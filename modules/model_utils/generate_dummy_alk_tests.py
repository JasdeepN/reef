import random
from datetime import datetime, timedelta
from app import app, db
from modules.models import TestResults, Tank

def prompt_yes_no(question):
    while True:
        ans = input(question + ' [y/n]: ').strip().lower()
        if ans in ('y', 'yes'):
            return True
        elif ans in ('n', 'no'):
            return False

def generate_dummy_tanks():
    """Create a few dummy tanks if they don't exist, or prompt to drop/recreate if they do."""
    tank_data = [
        {'id': 2, 'name': 'Test Tank 1', 'gross_water_vol': 100, 'net_water_vol': 90, 'live_rock_lbs': 50},
        {'id': 3, 'name': 'Test Tank 2', 'gross_water_vol': 120, 'net_water_vol': 110, 'live_rock_lbs': 60},
        {'id': 4, 'name': 'Test Tank 3', 'gross_water_vol': 80, 'net_water_vol': 70, 'live_rock_lbs': 40},
    ]
    existing = [Tank.query.get(t['id']) for t in tank_data]
    if any(existing):
        print("Some test tank IDs already exist in the database.")
        if prompt_yes_no("Drop all test tanks and their test results and regenerate? This will delete all data for tanks 2, 3, 4!"):
            # Delete test results and tanks
            from modules.models import TestResults, DSchedule, Dosing
            for tid in [2, 3, 4]:
                TestResults.query.filter_by(tank_id=tid).delete()
                Dosing.query.filter_by(product_id=tid).delete()
                DSchedule.query.filter_by(tank_id=tid).delete()
                Tank.query.filter_by(id=tid).delete()
            db.session.commit()
            print("Test tanks and related data dropped.")
        else:
            print("Skipping tank/test data generation.")
            return False
    # Create tanks
    for t in tank_data:
        tank = db.session.get(Tank, t['id'])
        if not tank:
            tank = Tank(id=t['id'], name=t['name'], gross_water_vol=t['gross_water_vol'], net_water_vol=t['net_water_vol'], live_rock_lbs=t['live_rock_lbs'])
            db.session.add(tank)
    db.session.commit()
    print("Dummy tanks created/verified.")
    return True

def generate_dummy_tests(tank_id, n_tests=30, days_back=45, data_quality=1.0):
    """
    data_quality: 0.0 = perfect/constant, 1.0 = realistic, >1.0 = very noisy
    """
    today = datetime.now().date()
    test_dates = set()
    # Randomly select 30 unique days in the last 45 days
    while len(test_dates) < n_tests:
        offset = random.randint(0, days_back-1)
        test_dates.add(today - timedelta(days=offset))
    test_dates = sorted(test_dates)
    for test_date in test_dates:
        # Alkalinity in typical reef range: 7.5 - 9.5 dKH
        alk = round(random.uniform(8.5 - 1.0*data_quality, 8.5 + 1.0*data_quality), 2)
        alk = max(0, alk)
        # Phosphate (ppm): 0.01 - 0.1, Phosphate (ppb): 10 - 100
        po4_ppm = round(random.uniform(0.05 - 0.04*data_quality, 0.05 + 0.04*data_quality), 3)
        po4_ppm = max(0, po4_ppm)
        po4_ppb = round((po4_ppm * 1000), 1)
        po4_ppb = max(0, po4_ppb)
        # Nitrate (ppm): 1 - 20
        no3_ppm = round(random.uniform(10 - 9*data_quality, 10 + 9*data_quality), 2)
        no3_ppm = max(0, no3_ppm)
        # Calcium (ppm): 380 - 450
        cal = int(random.uniform(415 - 35*data_quality, 415 + 35*data_quality))
        cal = max(0, cal)
        # Magnesium (ppm): 1200 - 1400
        mg = round(random.uniform(1300 - 100*data_quality, 1300 + 100*data_quality), 1)
        mg = max(0, mg)
        # Specific Gravity: 1.023 - 1.026
        sg = round(random.uniform(1.0245 - 0.0015*data_quality, 1.0245 + 0.0015*data_quality), 3)
        sg = max(0, sg)
        # Random time in the day
        hour = random.randint(8, 20)
        minute = random.randint(0, 59)
        test_time = datetime.combine(test_date, datetime.min.time()).replace(hour=hour, minute=minute).time()
        test = TestResults(
            test_date=test_date,
            test_time=test_time,
            alk=alk,
            po4_ppm=po4_ppm,
            po4_ppb=po4_ppb,
            no3_ppm=no3_ppm,
            cal=cal,
            mg=mg,
            sg=sg,
            tank_id=tank_id
        )
        db.session.add(test)
    db.session.commit()
    print(f"Inserted {n_tests} dummy test results for tank {tank_id} (data_quality={data_quality}).")
    # Print summary for this tank
    total = TestResults.query.filter_by(tank_id=tank_id).count()
    print(f"Total test results for tank {tank_id}: {total}")
    # Print all tests for this tank
    # all_tests = TestResults.query.filter_by(tank_id=tank_id).order_by(TestResults.test_date.asc(), TestResults.test_time.asc()).all()
    # print(f"All test results for tank {tank_id}:")
    # for t in all_tests:
    #     print(f"Date: {t.test_date}, Time: {t.test_time}, Alk: {t.alk}, PO4_ppm: {t.po4_ppm}, PO4_ppb: {t.po4_ppb}, NO3_ppm: {t.no3_ppm}, Ca: {t.cal}, Mg: {t.mg}, SG: {t.sg}")

def generate_dummy_schedules():
    """Create a dummy dosing schedule for each test tank and a dummy product."""
    from modules.models import Products, DSchedule
    # Create a dummy product for each tank if not exists
    for tid in [2, 3, 4]:
        prod = Products.query.filter_by(name=f"Test Product {tid}").first()
        if not prod:
            prod = Products(name=f"Test Product {tid}", uses='+Alk', total_volume=1000, current_avail=1000, dry_refill=0)
            # Do NOT set used_amt here; it is a generated column in the DB
            db.session.add(prod)
            db.session.commit()
        # Create a schedule
        sched = DSchedule.query.filter_by(tank_id=tid, products_id=prod.id).first()
        if not sched:
            sched = DSchedule(trigger_interval=24*60*60, suspended=False, last_refill=None, amount=10, tank_id=tid, products_id=prod.id)
            db.session.add(sched)
    db.session.commit()
    print("Dummy dosing schedules created/verified.")
    # Print all schedules for each tank
    from modules.models import Tank, DSchedule, Products
    for tid in [2, 3, 4]:
        tank = db.session.get(Tank, tid)
        if tank:
            schedules = DSchedule.query.filter_by(tank_id=tid).all()
            print(f"Tank {tid} ({tank.name}) schedules:")
            for sched in schedules:
                prod = db.session.get(Products, sched.products_id)
                prod_name = prod.name if prod else 'Unknown'
                print(f"  Schedule ID: {sched.id}, Product: {prod_name}, Interval: {sched.trigger_interval}, Amount: {sched.amount}, Suspended: {sched.suspended}")

if __name__ == "__main__":
    with app.app_context():
        if generate_dummy_tanks():
            generate_dummy_schedules()
            # Example: generate high-quality (low-noise) data
            generate_dummy_tests(tank_id=2, data_quality=0.2)
            # Example: generate realistic data
            generate_dummy_tests(tank_id=3, data_quality=1.0)
            # Example: generate very noisy data
            generate_dummy_tests(tank_id=4, data_quality=2.0)