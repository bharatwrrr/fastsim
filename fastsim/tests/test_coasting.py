"""
Tests that check the drive cycle modification functionality.
"""
import unittest

import numpy as np
from numpy.polynomial import Chebyshev

import fastsim


DO_PLOTS = False


def make_coasting_plot(cyc0, cyc, use_mph=False, save_file=None, do_show=False):
    """
    - cyc0: Cycle, the reference cycle (the "shadow trace" or "lead vehicle")
    - cyc: Cycle, the actual cycle driven
    - use_mph: Bool, if True, plot in miles per hour, else m/s
    - save_file: (Or None string), if specified, save the file to disk
    - do_show: Bool, whether to show the file or not
    RETURN: None
    - saves creates the given file and shows it
    """
    import matplotlib.pyplot as plt
    ts_orig = cyc0.cycSecs
    vs_orig = cyc0.cycMps
    m = fastsim.params.mphPerMps if use_mph else 1.0
    ds_orig = cyc0.cycDistMeters_v2.cumsum()
    ts = cyc.cycSecs
    vs = cyc.cycMps
    ds = cyc.cycDistMeters_v2.cumsum()
    gaps = ds_orig - ds
    speed_units = "mph" if use_mph else "m/s"
    (fig, axs) = plt.subplots(nrows=3)
    ax = axs[1]
    ax.plot(ts_orig, vs_orig * m, 'gray', label='shadow-trace')
    ax.plot(ts, vs * m, 'blue', label='coast')
    ax.plot(ts, vs * m, 'r.')
    ax.set_xlabel('Elapsed Time (s)')
    ax.set_ylabel(f'Speed ({speed_units})')
    ax.legend(loc=0, prop={'size': 6})
    ax = axs[2]
    ax.plot(ds_orig, vs_orig * m, 'gray', label='shadow-trace')
    ax.plot(ds, vs * m, 'blue', label='coast')
    ax.plot(ds, vs * m, 'r.')
    ax.set_xlabel('Distance Traveled (m)')
    ax.set_ylabel(f'Speed ({speed_units})')
    ax = axs[0]
    ax.plot(ts_orig, gaps, 'gray', label='shadow-trace')
    ax.set_xlabel('Elapsed Time (s)')
    ax.set_ylabel('Gap (m)')
    fig.tight_layout()
    print(f'Distance Traveled for Coasting Vehicle: {ds.sum()} m')
    print(f'Distance Traveled for Cycle           : {ds_orig.sum()} m')
    if save_file is not None:
        fig.savefig(save_file, dpi=300)
    if do_show:
        plt.show()
    plt.close()


def make_dvdd_plot(
    cyc,
    coast_to_break_speed_m__s=None,
    use_mph=False,
    save_file=None,
    do_show=False,
    curve_fit=True,
    additional_xs=None, additional_ys=None):
    """
    """
    if coast_to_break_speed_m__s is None:
        coast_to_break_speed_m__s = 5.0 # m/s
    TOL = 1e-6
    import matplotlib.pyplot as plt
    dvs = cyc.cycMps[1:] - cyc.cycMps[:-1]
    vavgs = 0.5 * (cyc.cycMps[1:] + cyc.cycMps[:-1])
    grades = cyc.cycGrade[:-1]
    unique_grades = np.sort(np.unique(grades))
    dds = vavgs * cyc.secs[1:]
    ks = dvs / dds
    ks[dds<TOL] = 0.0

    fig, ax = plt.subplots()
    m = fastsim.params.mphPerMps if use_mph else 1.0
    speed_units = "mph" if use_mph else "m/s"
    c1 = None
    c2 = None
    c3 = None
    if curve_fit:
        print("FITS:")
    for g in unique_grades:
        grade_pct = g * 100.0 # percentage
        mask = np.logical_and(
            np.logical_and(
                grades == g,
                ks < 0.0
            ),
            vavgs >= coast_to_break_speed_m__s
        )
        ax.plot(vavgs[mask] * m, np.abs(ks[mask]), label=f'{grade_pct}%')
        if curve_fit:
            c1 = Chebyshev.fit(vavgs[mask], ks[mask], deg=1)
            c2 = Chebyshev.fit(vavgs[mask], ks[mask], deg=2)
            c3 = Chebyshev.fit(vavgs[mask], ks[mask], deg=3)
            print(f"{g}: {c3}")
            colors = ['r', 'k', 'g']
            for deg, c in enumerate([c1, c2, c3]):
                if deg == 2:
                    xs, ys = c.linspace(n=25)
                    ax.plot(
                        xs,
                        np.abs(ys),
                        marker='.',
                        markerfacecolor=colors[deg],
                        markeredgecolor=colors[deg],
                        linestyle='None',
                        label=f'{grade_pct}% (fit {deg+1})')
    if additional_xs is not None and additional_ys is not None:
        ax.plot(additional_xs, additional_ys, 'r--', label='custom')
    ax.legend()
    ax.set_xlabel(f'Average Step Speed ({speed_units})')
    ax.set_ylabel('k-factor (m/s / m)')
    title = 'K by Speed and Grade'
    ax.set_title(title)
    fig.tight_layout()
    if save_file is not None:
        fig.savefig(save_file, dpi=300)
    if do_show:
        plt.show()
    plt.close()


class TestCoasting(unittest.TestCase):
    def setUp(self) -> None:
        # create a trapezoidal trip shape
        # initial ramp: d(t=10s) = 100 meters distance
        # distance by time in constant speed region = d(t) = 100m + (t - 10s) * 20m/s 
        # distance of stop: 100m + (45s - 10s) * 20m/s + 0.5 * (55s - 45s) * 20m/s = 900m
        self.distance_of_stop_m = 900.0
        trapz = fastsim.cycle.make_cycle(
            [0.0, 10.0, 45.0, 55.0, 100.0],
            [0.0, 20.0, 20.0, 0.0, 0.0],
        )
        trapz = fastsim.cycle.resample(trapz, new_dt=1.0)
        self.trapz = fastsim.cycle.Cycle(cyc_dict=trapz)
        self.veh = fastsim.vehicle.Vehicle(5, verbose=False)
        self.sim_drive = fastsim.simdrive.SimDriveClassic(self.trapz, self.veh)
        self.sim_drive_coast = fastsim.simdrive.SimDriveClassic(self.trapz, self.veh)
        self.sim_drive_coast.sim_params.allow_coast = True
        self.sim_drive_coast.sim_params.coast_start_speed_m__s = 17.0
        self.sim_drive_coast.sim_params.verbose = False
        return super().setUp()
    
    def tearDown(self) -> None:
        return super().tearDown()

    def test_cycle_reported_distance_traveled_m(self):
        ""
        # At the entering of constant-speed region
        idx = 10
        expected_time_s = 10.0
        t = self.trapz.cycSecs[idx]
        self.assertAlmostEqual(expected_time_s, t)
        expected_distance_m = 100.0
        dist_m = self.trapz.cycDistMeters_v2[:(idx + 1)].sum()
        self.assertAlmostEqual(expected_distance_m, dist_m)
        # At t=20s
        idx = 20
        expected_time_s = 20.0
        t = self.trapz.cycSecs[idx]
        self.assertAlmostEqual(expected_time_s, t)
        expected_distance_m = 300.0 # 100m + (20s - 10s) * 20m/s
        dist_m = self.trapz.cycDistMeters_v2[:(idx + 1)].sum()
        self.assertAlmostEqual(expected_distance_m, dist_m)
        dts = fastsim.cycle.calc_distance_to_next_stop(dist_m, self.trapz)
        dts_expected_m = 900 - dist_m
        self.assertAlmostEqual(dts_expected_m, dts)

    def test_cycle_modifications_with_constant_jerk(self):
        ""
        idx = 20
        n = 10
        accel = -1.0
        jerk = 0.1
        trapz = self.trapz.copy()
        fastsim.cycle.modify_cycle_with_trajectory(
            trapz, idx, n, jerk, -1.0
        )
        self.assertNotEqual(self.trapz.cycMps[idx], trapz.cycMps[idx])
        self.assertEqual(len(self.trapz.cycMps), len(trapz.cycMps))
        self.assertTrue(self.trapz.cycMps[idx] > trapz.cycMps[idx])
        v0 = trapz.cycMps[idx-1]
        v = v0
        a = accel
        for i in range(len(self.trapz.cycSecs)):
            msg = f"i: {i}; idx: {idx}; idx+n: {idx+n}"
            if i < idx or i >= idx+n:
                self.assertEqual(self.trapz.cycMps[i], trapz.cycMps[i], msg)
            else:
                dt = trapz.secs[idx]
                a_expected = fastsim.cycle.accel_for_constant_jerk(i - idx, accel, jerk, dt)
                a = accel + (i - idx) * jerk * dt
                v += a * dt
                msg += f" a: {a}, v: {v}, dt: {dt}"
                self.assertAlmostEqual(a_expected, a, msg=msg)
                self.assertAlmostEqual(v, trapz.cycMps[i], msg=msg)
    
    def test_that_cycle_modifications_work_as_expected(self):
        ""
        idx = 20
        n = 10
        accel = -1.0
        jerk = 0.0
        trapz = self.trapz.copy()
        fastsim.cycle.modify_cycle_with_trajectory(
            trapz, idx, n, jerk, -1.0
        )
        self.assertNotEqual(self.trapz.cycMps[idx], trapz.cycMps[idx])
        self.assertEqual(len(self.trapz.cycMps), len(trapz.cycMps))
        self.assertTrue(self.trapz.cycMps[idx] > trapz.cycMps[idx])
        for i in range(len(self.trapz.cycSecs)):
            msg = f"i: {i}; idx: {idx}; idx+n: {idx+n}"
            if i < idx or i >= idx+n:
                self.assertEqual(self.trapz.cycMps[i], trapz.cycMps[i])
            else:
                self.assertAlmostEqual(
                    self.trapz.cycMps[idx-1] + (accel * (i - idx + 1)),
                    trapz.cycMps[i]
                )
    
    def test_that_we_can_coast(self):
        "Test the standard interface to Eco-Approach for 'free coasting'"
        self.assertFalse(self.sim_drive.impose_coast.any(), "All impose_coast starts out False")
        while self.sim_drive_coast.i < len(self.trapz.cycSecs):
            self.sim_drive_coast.sim_drive_step()
        max_trace_miss_coast_m__s = np.absolute(self.trapz.cycMps - self.sim_drive_coast.mpsAch).max()
        self.assertTrue(max_trace_miss_coast_m__s > 1.0, f"Max trace miss: {max_trace_miss_coast_m__s} m/s")
        self.assertFalse(self.sim_drive_coast.impose_coast[0])
        if DO_PLOTS:
            make_coasting_plot(
                self.sim_drive_coast.cyc0,
                self.sim_drive_coast.cyc,
                use_mph=False,
                save_file='junk-test-that-we-can-coast.png')

    def test_eco_approach_modeling(self):
        "Test a simplified model of eco-approach"
        self.sim_drive_coast.sim_drive()
        self.assertFalse(self.sim_drive_coast.impose_coast.all(), "Assert we are not always in coast")
        self.assertTrue(self.sim_drive_coast.impose_coast.any(), "Assert we are at least sometimes in coast")
        max_trace_miss_coast_m__s = np.absolute(self.trapz.cycMps - self.sim_drive_coast.mpsAch).max()
        self.assertTrue(max_trace_miss_coast_m__s > 1.0, "Assert we deviate from the shadow trace")
        self.assertTrue(self.sim_drive_coast.mphAch.max() > 20.0, "Assert we at least reach 20 mph")
        # TODO: can we increase the precision of matching?
        self.assertAlmostEqual(
            self.trapz.cycDistMeters.sum(),
            self.sim_drive_coast.distMeters.sum(), 0,
            "Assert the end distances are equal\n" +
            f"Got {self.trapz.cycDistMeters.sum()} m and {self.sim_drive_coast.distMeters.sum()} m")

    def test_consistency_of_constant_jerk_trajectory(self):
        "Confirm that acceleration, speed, and distances are as expected for constant jerk trajectory"
        n = 10 # ten time-steps
        v0 = 15.0
        vr = 7.5
        d0 = 0.0
        dr = 120.0
        dt = 1.0
        trajectory = fastsim.cycle.calc_constant_jerk_trajectory(n, d0, v0, dr, vr, dt)
        a0 = trajectory['accel_m__s2']
        k = trajectory['jerk_m__s3']
        v = v0
        d = d0
        a = a0
        vs = [v0]
        for n in range(n):
            a_expected = fastsim.cycle.accel_for_constant_jerk(n, a0, k, dt)
            v_expected = fastsim.cycle.speed_for_constant_jerk(n, v0, a0, k, dt)
            d_expected = fastsim.cycle.dist_for_constant_jerk(n, d0, v0, a0, k, dt)
            if n > 0:
                d += dt * (v + v + a * dt) / 2.0
                v += a * dt
            # acceleration is the constant acceleration for the NEXT time-step
            a = a0 + n * k * dt
            self.assertAlmostEqual(a, a_expected)
            self.assertAlmostEqual(v, v_expected)
            self.assertAlmostEqual(d, d_expected)

    def test_that_final_speed_of_cycle_modification_matches_trajectory_calcs(self):
        ""
        trapz = self.trapz.copy()
        idx = 20
        n = 20
        d0 = self.trapz.cycDistMeters[:idx].sum()
        v0 = self.trapz.cycMps[idx-1]
        dt = self.trapz.secs[idx]
        brake_decel_m__s2 = 2.5
        dts0 = fastsim.cycle.calc_distance_to_next_stop(d0, trapz)
        # speed at which friction braking initiates (m/s)
        brake_start_speed_m__s = 7.5
        # distance to brake (m)
        dtb = 0.5 * brake_start_speed_m__s * brake_start_speed_m__s / brake_decel_m__s2
        dtbi0 = dts0 - dtb
        trajectory = fastsim.cycle.calc_constant_jerk_trajectory(n, d0, v0, d0 + dtbi0, brake_start_speed_m__s, dt)
        final_speed_m__s = fastsim.cycle.modify_cycle_with_trajectory(
            self.trapz,
            idx,
            n,
            trajectory['jerk_m__s3'],
            trajectory['accel_m__s2'])
        self.assertAlmostEqual(final_speed_m__s, brake_start_speed_m__s)

    def test_that_cycle_distance_reported_is_correct(self):
        ""
        # total distance
        d_expected = 900.0
        d_v1 = self.trapz.cycDistMeters.sum()
        d_v2 = self.trapz.cycDistMeters_v2.sum()
        self.assertAlmostEqual(d_expected, d_v1)
        self.assertAlmostEqual(d_expected, d_v2)
        # distance traveled between 0 s and 10 s
        d_expected = 100.0 # 0.5 * (0s - 10s) * 20m/s = 100m
        d_v1 = self.trapz.cycDistMeters[:11].sum()
        d_v2 = self.trapz.cycDistMeters_v2[:11].sum()
        # TODO: is there a way to get the distance from 0 to 10s using existing cycDistMeters system?
        self.assertNotEqual(d_expected, d_v1)
        self.assertAlmostEqual(d_expected, d_v2)
        # distance traveled between 10 s and 45 s
        d_expected = 700.0 # (45s - 10s) * 20m/s = 700m
        d_v1 = self.trapz.cycDistMeters[11:46].sum()
        d_v2 = self.trapz.cycDistMeters_v2[11:46].sum()
        self.assertAlmostEqual(d_expected, d_v1)
        self.assertAlmostEqual(d_expected, d_v2)
        # distance traveled between 45 s and 55 s
        d_expected = 100.0 # 0.5 * (45s - 55s) * 20m/s = 100m
        d_v1 = self.trapz.cycDistMeters[45:56].sum()
        d_v2 = self.trapz.cycDistMeters_v2[46:56].sum()
        # TODO: is there a way to get the distance from 45 to 55s using existing cycDistMeters system?
        self.assertNotEqual(d_expected, d_v1)
        self.assertAlmostEqual(d_expected, d_v2)
        # TRIANGLE RAMP SPEED CYCLE
        const_spd_cyc = fastsim.cycle.Cycle(
            cyc_dict=fastsim.cycle.resample(
                fastsim.cycle.make_cycle(
                    [0.0, 20.0],
                    [0.0, 20.0]
                ),
                new_dt=1.0
            )
        )
        expected_dist_m = 200.0 # 0.5 * 20m/s x 20s = 200m
        self.assertAlmostEqual(expected_dist_m, const_spd_cyc.cycDistMeters_v2.sum())
        self.assertNotEqual(expected_dist_m, const_spd_cyc.cycDistMeters.sum())

    def test_brake_trajectory(self):
        ""
        trapz = self.trapz.copy()
        brake_accel_m__s2 = -2.0
        idx = 30
        dt = 1.0
        v0 = trapz.cycMps[idx]
        # distance required to stop (m)
        expected_dts_m = 0.5 * v0 * v0 / abs(brake_accel_m__s2)
        tts_s = -v0 / brake_accel_m__s2
        n = int(np.ceil(tts_s / dt))
        fastsim.cycle.modify_cycle_adding_braking_trajectory(trapz, brake_accel_m__s2, idx+1)
        self.assertAlmostEqual(v0, trapz.cycMps[idx])
        self.assertAlmostEqual(v0 + brake_accel_m__s2*dt, trapz.cycMps[idx+1])
        self.assertAlmostEqual(v0 + brake_accel_m__s2*2*dt, trapz.cycMps[idx+2])
        self.assertAlmostEqual(v0 + brake_accel_m__s2*3*dt, trapz.cycMps[idx+3])
        self.assertAlmostEqual(v0 + brake_accel_m__s2*4*dt, trapz.cycMps[idx+4])
        self.assertAlmostEqual(v0 + brake_accel_m__s2*5*dt, trapz.cycMps[idx+5])
        self.assertAlmostEqual(v0 + brake_accel_m__s2*6*dt, trapz.cycMps[idx+6])
        self.assertAlmostEqual(v0 + brake_accel_m__s2*7*dt, trapz.cycMps[idx+7])
        self.assertAlmostEqual(v0 + brake_accel_m__s2*8*dt, trapz.cycMps[idx+8])
        self.assertAlmostEqual(v0 + brake_accel_m__s2*9*dt, trapz.cycMps[idx+9])
        self.assertAlmostEqual(v0 + brake_accel_m__s2*10*dt, trapz.cycMps[idx+10])
        self.assertEqual(10, n)
        self.assertAlmostEqual(20.0, trapz.cycMps[idx+11])
        dts_m = trapz.cycDistMeters_v2[idx+1:idx+n+1].sum()
        self.assertAlmostEqual(expected_dts_m, dts_m)
        # Now try with a brake deceleration that doesn't devide evenly by time-steps
        trapz = self.trapz.copy()
        brake_accel_m__s2 = -1.75
        idx = 30
        dt = 1.0
        v0 = trapz.cycMps[idx]
        # distance required to stop (m)
        expected_dts_m = 0.5 * v0 * v0 / abs(brake_accel_m__s2)
        tts_s = -v0 / brake_accel_m__s2
        n = int(np.ceil(tts_s / dt))
        fastsim.cycle.modify_cycle_adding_braking_trajectory(trapz, brake_accel_m__s2, idx+1)
        self.assertAlmostEqual(v0, trapz.cycMps[idx])
        self.assertEqual(12, n)
        dts_m = trapz.cycDistMeters_v2[idx+1:idx+n+1].sum()
        self.assertAlmostEqual(expected_dts_m, dts_m)
    
    def test_logic_to_enter_eco_approach_automatically(self):
        "Test that we can auto-enter eco-approach"
        trapz = self.trapz.copy()
        veh = fastsim.vehicle.Vehicle(5, verbose=False)
        sd = fastsim.simdrive.SimDriveClassic(trapz, veh)
        sd.sim_params.allow_coast = True
        sd.sim_params.coast_start_speed_m__s = -1
        sd.sim_params.verbose = False
        sd.sim_params.coast_to_brake_speed_m__s = 4.0
        sd.sim_drive()
        self.assertTrue(sd.impose_coast.any(), msg="Coast should initiate automatically")
        if DO_PLOTS:
            make_coasting_plot(
                sd.cyc0,
                sd.cyc,
                use_mph=False,
                save_file='junk-test-logic-to-enter-eco-approach-automatically-1.png')
        trapz2 = fastsim.cycle.Cycle(
            cyc_dict=fastsim.cycle.resample(
                fastsim.cycle.make_cycle(
                    [0.0, 10.0, 200.0, 210.0, 300.0],
                    [0.0, 20.0, 20.0, 0.0, 0.0],
                ),
                new_dt=1.0
            )
        )
        veh = fastsim.vehicle.Vehicle(5, verbose=False)
        sd = fastsim.simdrive.SimDriveClassic(trapz2, veh)
        sd.sim_params.allow_coast = True
        sd.sim_params.coast_start_speed_m__s = -1
        sd.sim_params.coast_to_brake_speed_m__s = 4.0
        sd.sim_params.verbose = False
        sd.sim_drive()
        self.assertTrue(sd.impose_coast.any(), msg="Coast should initiate automatically")
        if DO_PLOTS:
            make_coasting_plot(
                sd.cyc0,
                sd.cyc,
                use_mph=False,
                save_file='junk-test-logic-to-enter-eco-approach-automatically-2.png')
            make_dvdd_plot(
                sd.cyc,
                use_mph=False,
                save_file='junk-test-logic-to-enter-eco-approach-automatically-3-dvdd.png',
                coast_to_break_speed_m__s=11.0
            )

    def test_that_coasting_works_going_uphill(self):
        "Test coasting logic while hill climbing"
        trapz = fastsim.cycle.Cycle(
            cyc_dict=fastsim.cycle.resample(
                fastsim.cycle.make_cycle(
                    [0.0, 10.0, 45.0, 55.0, 100.0],
                    [0.0, 20.0, 20.0, 0.0, 0.0],
                    [0.01, 0.01, 0.01, 0.01, 0.01],
                ),
                new_dt=1.0,
                hold_keys={'cycGrade'},
            )
        )
        veh = fastsim.vehicle.Vehicle(5, verbose=False)
        sd = fastsim.simdrive.SimDriveClassic(trapz, veh)
        sd.sim_params.allow_coast = True
        sd.sim_params.coast_start_speed_m__s = -1
        sd.sim_params.coast_to_brake_speed_m__s = 4.0
        sd.sim_params.verbose = False
        sd.sim_drive()
        self.assertTrue(sd.impose_coast.any(), msg="Coast should initiate automatically")
        if DO_PLOTS:
            vavgs = np.linspace(5.0, 40.0, endpoint=True)
            grade = 0.01
            def dvdd(vavg, grade):
                atan_grade = float(np.arctan(grade))
                g = sd.props.gravityMPerSec2
                M = veh.vehKg
                rho_CDFA = sd.props.airDensityKgPerM3 * veh.frontalAreaM2 * veh.dragCoef
                return (
                    (g/vavg) * (np.sin(atan_grade) + veh.wheelRrCoef * np.cos(atan_grade))
                    + (0.5 * rho_CDFA * (1.0/M) * vavg)
                )
            ks = [dvdd(vavg, grade) for vavg in vavgs]
            make_coasting_plot(
                sd.cyc0,
                sd.cyc,
                use_mph=False,
                save_file='junk-test_that_coasting_works_going_uphill-trace.png')
            make_dvdd_plot(
                sd.cyc,
                use_mph=False,
                save_file='junk-test_that_coasting_works_going_uphill-dvdd.png',
                coast_to_break_speed_m__s=5.0,
                additional_xs=vavgs,
                additional_ys=ks
            )
        if False:
            self.assertAlmostEqual(
                sd.cyc0.cycDistMeters_v2.sum(),
                sd.cyc.cycDistMeters_v2.sum(),
                msg="Should still cover the same distance when coasting as parent cycle"
            )

    def test_that_distance_to_stop_by_coast_works_as_expected(self):
        "Testing the fundamental distance to stop via coast function"
        v0 = 5.0
        v_brake = 7.5
        a_brake = -2.5
        M = self.veh.vehKg
        rho = self.sim_drive.props.airDensityKgPerM3
        g = self.sim_drive.props.gravityMPerSec2
        CD = self.veh.dragCoef
        FA = self.veh.frontalAreaM2
        rrc = self.veh.wheelRrCoef
        dt = 1.0
        d = fastsim.cycle.calc_distance_to_stop_coast_v2(
            v0, v_brake, a_brake,
            distances_m=np.array([0.0, 100_000.0]),
            grade_by_distance=np.array([0.0, 0.0]),
            veh_mass_kg=M, air_density_kg__m3=rho, CDFA_m2=CD*FA,
            rrc=rrc, gravity_m__s2=g, dt_s=dt
        )
        expected_d = -0.5 * (v0 * v0) / a_brake
        self.assertAlmostEqual(expected_d, d)
        v0 = v_brake
        d = fastsim.cycle.calc_distance_to_stop_coast_v2(
            v0, v_brake, a_brake,
            distances_m=np.array([0.0, 100_000.0]),
            grade_by_distance=np.array([0.0, 0.0]),
            veh_mass_kg=M, air_density_kg__m3=rho, CDFA_m2=CD*FA,
            rrc=rrc, gravity_m__s2=g, dt_s=dt
        )
        expected_d = -0.5 * (v0 * v0) / a_brake
        self.assertAlmostEqual(expected_d, d)
        v0 = 20.0
        M = 10000.0 # set easier-to-compute mass
        rrc = 0.1 # set easier rrc
        g = 10.0 # make math easier
        rho = 0.0 # turn off aerodynamic drag
        k = fastsim.cycle.calc_dvdd(v0, 0.0, M, rho, CD*FA, rrc, g)
        expected_k = -1 * (g/v0) * rrc
        self.assertAlmostEqual(expected_k, k)
        d = fastsim.cycle.calc_distance_to_stop_coast_v2(
            v0, v_brake, a_brake,
            distances_m=np.array([0.0, 100_000.0]),
            grade_by_distance=np.array([0.0, 0.0]),
            veh_mass_kg=M, air_density_kg__m3=rho, CDFA_m2=CD*FA,
            rrc=rrc, gravity_m__s2=g, dt_s=dt
        )
        self.assertTrue(d is not None)
        expected_d = (1.0/(rrc*g)) * 0.5 * (v0*v0 - v_brake*v_brake) + -0.5 * (v0 * v0) / a_brake
        self.assertAlmostEqual(expected_d, d)
        
    def test_that_coasting_logic_works_going_uphill(self):
        "When going uphill, we want to ensure we can still hit our coasting target"
        trapz = fastsim.cycle.Cycle(
            cyc_dict=fastsim.cycle.resample(
                fastsim.cycle.make_cycle(
                    [0.0, 10.0, 45.0, 55.0, 100.0],
                    [0.0, 20.0, 20.0, 0.0, 0.0],
                    [0.01, 0.01, 0.01, 0.01, 0.01],
                ),
                new_dt=1.0,
                hold_keys={'cycGrade'},
            )
        )
        veh = fastsim.vehicle.Vehicle(5, verbose=False)
        print(f'veh mass (kg): {veh.vehKg}')
        sd = fastsim.simdrive.SimDriveClassic(trapz, veh)
        sd.sim_params.allow_coast = True
        sd.sim_params.coast_start_speed_m__s = -1
        sd.sim_params.coast_to_brake_speed_m__s = 4.0
        sd.sim_params.verbose = False
        sd.sim_drive()
        self.assertTrue(sd.impose_coast.any(), msg="Coast should initiate automatically")
        if True or DO_PLOTS:
            make_coasting_plot(
                sd.cyc0,
                sd.cyc,
                use_mph=False,
                save_file='test_that_coasting_logic_works_going_uphill.png')
        # TODO: can we increase the precision?
        self.assertAlmostEqual(
            sd.cyc0.cycDistMeters_v2.sum(), sd.cyc.cycDistMeters.sum(), 0)
