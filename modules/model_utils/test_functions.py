def calculate_lanthanum_dose(tank_volume_liters, phosphate_reduction_ppm, la_cl3_concentration_mg_per_ml):
    """
    Calculate how much lanthanum chloride solution to dose.

    Parameters:
    - tank_volume_liters: Volume of the reef tank in liters
    - phosphate_reduction_ppm: Desired reduction in phosphate (in mg/L or ppm)
    - la_cl3_concentration_mg_per_ml: Concentration of the LaCl3 dosing solution in mg/mL

    Returns:
    - volume_to_dose_ml: Volume of LaCl3 solution to dose (in mL)
    """

    # Step 1: Calculate the total phosphate mass to remove
    phosphate_mass_mg = phosphate_reduction_ppm * tank_volume_liters

    # Step 2: Stoichiometric conversion factor (1 mg LaCl3 removes ~0.387 mg PO4)
    la_cl3_needed_mg = phosphate_mass_mg / 0.387

    # Step 3: Calculate dose volume
    volume_to_dose_ml = la_cl3_needed_mg / la_cl3_concentration_mg_per_ml

    return volume_to_dose_ml


# Example usage
tank_volume_liters = 378.5  # 100 gallons
phosphate_reduction_ppm = 0.1  # Desired PO4 drop (mg/L)
la_cl3_concentration_mg_per_ml = 100  # 10% LaCl3 solution = 100 mg/mL approx.

dose_ml = calculate_lanthanum_dose(tank_volume_liters, phosphate_reduction_ppm, la_cl3_concentration_mg_per_ml)
print(f"Dose approximately {dose_ml:.2f} mL of LaCl₃ solution.")
