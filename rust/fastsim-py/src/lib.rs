use fastsim_core::*;

use pyo3imports::*;

/// Function for adding Rust structs as Python Classes
#[pymodule]
fn fastsimrust(py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<cycle::RustCycle>()?;
    m.add_class::<vehicle::RustVehicle>()?;
    m.add_class::<params::RustPhysicalProperties>()?;
    m.add_class::<utils::Pyo3ArrayU32>()?;
    m.add_class::<utils::Pyo3ArrayF64>()?;
    m.add_class::<utils::Pyo3ArrayBool>()?;
    m.add_class::<utils::Pyo3VecF64>()?;
    m.add_class::<simdrive::RustSimDriveParams>()?;
    m.add_class::<simdrive::RustSimDrive>()?;
    cycle::register(py, m)?;
    Ok(())
}
