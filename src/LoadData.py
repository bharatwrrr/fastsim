"""Module containing function for loading drive cycle data (e.g. speed trace)
and class (Vehicle) for loading and storing vehicle attribute data.  For example usage, 
see ../README.md"""

import pandas as pd
from Globals import *
import numpy as np
import re

class Cycle(object):
    """Object for containing time, speed, road grade, and road charging vectors 
    for drive cycle."""
    def __init__(self, std_cyc_name=None, cyc_dict=None):
        """Runs other methods, depending on provided keyword argument. Only one keyword
        argument should be provided.  Keyword arguments are identical to 
        arguments required by corresponding methods.  The argument 'std_cyc_name' can be
        optionally passed as a positional argument."""

        super().__init__()
        if std_cyc_name:
            self.set_standard_cycle(std_cyc_name)
        if cyc_dict:
            self.set_from_dict(cyc_dict)

    def set_standard_cycle(self, std_cyc_name):
        """Load time trace of speed, grade, and road type in a pandas dataframe.
        Argument:
        ---------
        std_cyc_name: cycle name string (e.g. 'udds', 'us06', 'hwfet')"""
        csv_path = '..//cycles//' + std_cyc_name + '.csv'
        cyc = pd.read_csv(csv_path)
        for column in cyc.columns:
            self.__setattr__(column, cyc[column].copy().to_numpy())
        self.set_dependents()

    def set_from_dict(self, cyc_dict):
        """Set cycle attributes from dict with keys 'cycGrade', 'cycMps', 'cycSecs', 'cycRoadType'
        and numpy arrays of equal length for values.
        Arguments
        ---------
        cyc_dict: dict containing cycle data
        """

        for key in cyc_dict.keys():
            self.__setattr__(key, cyc_dict[key])
        self.set_dependents()
    
    def set_dependents(self):
        """Sets values dependent on cycle info loaded from file."""
        self.cycMph = np.copy(self.cycMps * mphPerMps)
        self.secs = np.insert(np.diff(self.cycSecs), 0, 0)


class Vehicle(object):
    """Class for loading and contaning vehicle attributes
    Optional Argument:
    ---------
    vnum: row number of vehicle to simulate in 'FASTSim_py_veh_db.csv'"""

    def __init__(self, vnum=None):
        super().__init__()
        if vnum:
            self.load_vnum(vnum)
        
    def load_vnum(self, vnum):
        """Load vehicle parameters based on vnum and assign to self.
        Argument:
        ---------
        vnum: row number of vehicle to simulate in 'FASTSim_py_veh_db.csv'"""

        vehdf = pd.read_csv('..//docs//FASTSim_py_veh_db.csv')
        vehdf.set_index('Selection', inplace=True, drop=False)
        # vehdf = vehdf.loc[[vnum], :]

        def clean_data(raw_data):
            """Cleans up data formatting.
            Argument:
            ------------
            raw_data: cell of vehicle dataframe
            
            Output:
            clean_data: cleaned up data"""
            
            # convert data to string types
            data = str(raw_data)
            # remove percent signs if any are found
            if '%' in data:
                data = data.replace('%', '')
                data = float(data)
                data = data / 100.0
            # replace string for TRUE with Boolean True
            elif re.search('(?i)true', data) != None:
                data = True
            # replace string for FALSE with Boolean False
            elif re.search('(?i)false', data) != None:
                data = False
            else:
                try:
                    data = float(data)
                except:
                    pass
            
            return data
        
        vehdf.loc[vnum].apply(clean_data)

        ### selects specified vnum from vehdf
        for col in vehdf.columns:
            col1 = col.replace(' ', '_')
            
            # assign dataframe columns 
            self.__setattr__(col1, vehdf.loc[vnum, col])
        
        self.set_init_calcs()
        self.set_veh_mass()

    def set_init_calcs(self):
        """Set parameters that can be calculated after loading vehicle data"""
        ### Build roadway power lookup table
        self.MaxRoadwayChgKw_Roadway = range(6)
        self.MaxRoadwayChgKw = [0] * len(self.MaxRoadwayChgKw_Roadway)
        self.chargingOn = 0

        # Checking if a vehicle has any hybrid components
        if self.maxEssKwh == 0 or self.maxEssKw == 0 or self.maxMotorKw == 0:
            self.noElecSys = True

        else:
            self.noElecSys = False

        # Checking if aux loads go through an alternator
        if self.noElecSys == True or self.maxMotorKw <= self.auxKw or self.forceAuxOnFC == True:
            self.noElecAux = True

        else:
            self.noElecAux = False

        # Copying vehPtType to additional key
        self.vehTypeSelection = np.copy(self.vehPtType)
        # to be consistent with Excel version but not used in Python version

        ### Defining Fuel Converter efficiency curve as lookup table for %power_in vs power_out
        ### see "FC Model" tab in FASTSim for Excel

        if self.maxFuelConvKw > 0:

            # Power and efficiency arrays are defined in Globals.py
            
            if self.fcEffType == 1:  # SI engine
                eff = np.copy(eff_si) + self.fcAbsEffImpr

            elif self.fcEffType == 2:  # Atkinson cycle SI engine -- greater expansion
                eff = np.copy(eff_atk) + self.fcAbsEffImpr

            elif self.fcEffType == 3:  # Diesel (compression ignition) engine
                eff = np.copy(eff_diesel) + self.fcAbsEffImpr

            elif self.fcEffType == 4:  # H2 fuel cell
                eff = np.copy(eff_fuel_cell) + self.fcAbsEffImpr

            elif self.fcEffType == 5:  # heavy duty Diesel engine
                eff = np.copy(eff_hd_diesel) + self.fcAbsEffImpr

            # discrete array of possible engine power outputs
            inputKwOutArray = fcPwrOutPerc * self.maxFuelConvKw
            # Relatively continuous array of possible engine power outputs
            fcKwOutArray = self.maxFuelConvKw * fcPercOutArray
            # Initializes relatively continuous array for fcEFF
            fcEffArray = np.array([0.0] * len(fcPercOutArray))

            # the following for loop populates fcEffArray
            for j in range(0, len(fcPercOutArray) - 1):
                low_index = np.argmax(inputKwOutArray >= fcKwOutArray[j])
                fcinterp_x_1 = inputKwOutArray[low_index-1]
                fcinterp_x_2 = inputKwOutArray[low_index]
                fcinterp_y_1 = eff[low_index-1]
                fcinterp_y_2 = eff[low_index]
                fcEffArray[j] = (fcKwOutArray[j] - fcinterp_x_1)/(fcinterp_x_2 -
                                    fcinterp_x_1) * (fcinterp_y_2 - fcinterp_y_1) + fcinterp_y_1

            # populate final value
            fcEffArray[-1] = eff[-1]

            # assign corresponding values in veh dict
            self.fcEffArray = np.copy(fcEffArray)
            self.fcKwOutArray = np.copy(fcKwOutArray)
            self.maxFcEffKw = np.copy(self.fcKwOutArray[np.argmax(fcEffArray)])
            self.fcMaxOutkW = np.copy(max(inputKwOutArray))
            
        else:
            # these things are all zero for BEV powertrains
            # not sure why `self.fcEffArray` is not being assigned.
            # Maybe it's not used anywhere in this condition.  *** delete this comment before public release
            self.fcKwOutArray = np.array([0] * 101)
            self.maxFcEffKw = 0
            self.fcMaxOutkW = 0
            
        ### Defining MC efficiency curve as lookup table for %power_in vs power_out
        ### see "Motor" tab in FASTSim for Excel
        if self.maxMotorKw > 0:

            maxMotorKw = self.maxMotorKw
            
            # Power and efficiency arrays are defined in Globals.py

            modern_diff = modern_max - max(large_baseline_eff)

            large_baseline_eff_adj = large_baseline_eff + modern_diff

            mcKwAdjPerc = max(0.0, min((maxMotorKw - 7.5)/(75.0 - 7.5), 1.0))
            mcEffArray = np.array([0.0] * len(mcPwrOutPerc))

            for k in range(0, len(mcPwrOutPerc)):
                mcEffArray[k] = mcKwAdjPerc * large_baseline_eff_adj[k] + \
                    (1 - mcKwAdjPerc)*(small_baseline_eff[k])

            mcInputKwOutArray = mcPwrOutPerc * maxMotorKw
            mcFullEffArray = np.array([0.0] * len(mcPercOutArray))
            mcKwOutArray = np.linspace(0, 1, len(mcPercOutArray)) * maxMotorKw

            for m in range(1, len(mcPercOutArray) - 1):
                low_index = np.argmax(mcInputKwOutArray >= mcKwOutArray[m])

                fcinterp_x_1 = mcInputKwOutArray[low_index-1]
                fcinterp_x_2 = mcInputKwOutArray[low_index]
                fcinterp_y_1 = mcEffArray[low_index-1]
                fcinterp_y_2 = mcEffArray[low_index]

                mcFullEffArray[m] = (mcKwOutArray[m] - fcinterp_x_1)/(
                    fcinterp_x_2 - fcinterp_x_1)*(fcinterp_y_2 - fcinterp_y_1) + fcinterp_y_1

            mcFullEffArray[0] = 0
            mcFullEffArray[-1] = mcEffArray[-1]

            mcKwInArray = mcKwOutArray / mcFullEffArray
            mcKwInArray[0] = 0

            self.mcKwInArray = np.copy(mcKwInArray)
            self.mcKwOutArray = np.copy(mcKwOutArray)
            self.mcMaxElecInKw = np.copy(max(mcKwInArray))
            self.mcFullEffArray = np.copy(mcFullEffArray)
            self.mcEffArray = np.copy(mcEffArray)

            if 'motorAccelAssist' in self.__dir__() and np.isnan(self.__getattribute__('motorAccelAssist')):
                self.motorAccelAssist = True

        else:
            self.mcKwInArray = np.array([0.0] * len(mcPercOutArray))
            self.mcKwOutArray = np.array([0.0] * len(mcPercOutArray))
            self.mcMaxElecInKw = 0

        self.mcMaxElecInKw = max(self.mcKwInArray)

        ### Specify shape of mc regen efficiency curve
        ### see "Regen" tab in FASTSim for Excel
        self.regenA = 500.0  # hardcoded
        self.regenB = 0.99  # hardcoded

    def set_veh_mass(self):
        """Calculate total vehicle mass.  Sum up component masses if 
        positive real number is not specified for vehOverrideKg"""
        if not(self.vehOverrideKg > 0):
            if self.maxEssKwh == 0 or self.maxEssKw == 0:
                ess_mass_kg = 0.0
            else:
                ess_mass_kg = ((self.maxEssKwh * self.essKgPerKwh) +
                            self.essBaseKg) * self.compMassMultiplier
            if self.maxMotorKw == 0:
                mc_mass_kg = 0.0
            else:
                mc_mass_kg = (self.mcPeBaseKg+(self.mcPeKgPerKw
                                                * self.maxMotorKw)) * self.compMassMultiplier
            if self.maxFuelConvKw == 0:
                fc_mass_kg = 0.0
            else:
                fc_mass_kg = (((1 / self.fuelConvKwPerKg) * self.maxFuelConvKw +
                            self.fuelConvBaseKg)) * self.compMassMultiplier
            if self.maxFuelStorKw == 0:
                fs_mass_kg = 0.0
            else:
                fs_mass_kg = ((1 / self.fuelStorKwhPerKg) *
                            self.fuelStorKwh) * self.compMassMultiplier
            self.vehKg = self.cargoKg + self.gliderKg + self.transKg * \
                self.compMassMultiplier + ess_mass_kg + \
                mc_mass_kg + fc_mass_kg + fs_mass_kg
        # if positive real number is specified for vehOverrideKg, use that
        else:
            self.vehKg = np.copy(self.vehOverrideKg)
