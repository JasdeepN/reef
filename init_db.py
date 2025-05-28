#!/usr/bin/env python3
"""
Database Initialization Script for ReefDB
Creates all tables and populates with seed data for new containers.
"""

import os
import sys
import logging
from datetime import datetime, date, time
from decimal import Decimal

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def init_database():
    """Initialize the database with tables and seed data."""
    try:
        # Import after path setup
        from app import app, db
        from modules.models import (
            Tank, TestResults, Products, Dosing, DSchedule, 
            Coral, Taxonomy, Vendors, ColorMorphs, CareReqs, AlkalinityDoseModel
        )
        
        with app.app_context():
            logger.info("Creating database tables...")
            
            # Create all tables
            db.create_all()
            logger.info("Database tables created successfully")
            
            # Check if database already has data
            if Tank.query.first():
                logger.info("Database already contains data, skipping seed data insertion")
                return
            
            logger.info("Seeding database with initial data...")
            
            # Seed Tanks
            tanks = [
                Tank(name="Main Display Tank", gross_water_vol=120, net_water_vol=100, live_rock_lbs=25.0),
                Tank(name="Quarantine Tank", gross_water_vol=20, net_water_vol=18, live_rock_lbs=5.0),
                Tank(name="Frag Tank", gross_water_vol=40, net_water_vol=35, live_rock_lbs=10.0)
            ]
            
            for tank in tanks:
                db.session.add(tank)
            
            # Seed Vendors
            vendors = [
                Vendors(tag="WWC", name="World Wide Corals"),
                Vendors(tag="TSA", name="Tidal Sea Aquatics"),
                Vendors(tag="BC", name="Battlecorals"),
                Vendors(tag="ASD", name="Aqua SD"),
                Vendors(tag="LOCAL", name="Local Fish Store"),
                Vendors(tag="FRAG", name="Frag Swap"),
                Vendors(tag="DIY", name="Self Propagated")
            ]
            
            for vendor in vendors:
                db.session.add(vendor)
            
            # Seed Taxonomy
            taxonomies = [
                # SPS Corals
                Taxonomy(genus="Acropora", species="millepora", family="Acroporidae", type="SPS", common_name="Staghorn Coral"),
                Taxonomy(genus="Acropora", species="tenuis", family="Acroporidae", type="SPS", common_name="Slender Staghorn"),
                Taxonomy(genus="Montipora", species="digitata", family="Acroporidae", type="SPS", common_name="Velvet Finger Coral"),
                Taxonomy(genus="Stylophora", species="pistillata", family="Pocilloporidae", type="SPS", common_name="Hood Coral"),
                Taxonomy(genus="Pocillopora", species="damicornis", family="Pocilloporidae", type="SPS", common_name="Cauliflower Coral"),
                
                # LPS Corals
                Taxonomy(genus="Euphyllia", species="ancora", family="Euphylliidae", type="LPS", common_name="Hammer Coral"),
                Taxonomy(genus="Euphyllia", species="glabrescens", family="Euphylliidae", type="LPS", common_name="Torch Coral"),
                Taxonomy(genus="Trachyphyllia", species="geoffroyi", family="Trachyphylliidae", type="LPS", common_name="Open Brain Coral"),
                Taxonomy(genus="Lobophyllia", species="hemprichii", family="Lobophylliidae", type="LPS", common_name="Lobed Brain Coral"),
                
                # Soft Corals
                Taxonomy(genus="Sarcophyton", species="elegans", family="Alcyoniidae", type="Soft", common_name="Leather Coral"),
                Taxonomy(genus="Sinularia", species="flexibilis", family="Alcyoniidae", type="Soft", common_name="Finger Leather"),
                
                # Mushrooms
                Taxonomy(genus="Discosoma", species="neglecta", family="Discosomatidae", type="Mushroom", common_name="Mushroom Coral"),
                Taxonomy(genus="Rhodactis", species="indosinensis", family="Discosomatidae", type="Mushroom", common_name="Hairy Mushroom"),
                
                # Zoanthids
                Taxonomy(genus="Zoanthus", species="sociatus", family="Zoanthidae", type="Zoanthid", common_name="Button Polyp"),
                Taxonomy(genus="Palythoa", species="caribaeorum", family="Zoanthidae", type="Zoanthid", common_name="Brown Palythoa")
            ]
            
            for taxonomy in taxonomies:
                db.session.add(taxonomy)
            
            # Commit taxonomy and vendors first to get IDs
            db.session.commit()
            
            # Seed Color Morphs
            color_morphs = [
                ColorMorphs(taxonomy_id=1, morph_name="Blue Tip", description="Blue tips with green base", rarity="Common", source="Australia"),
                ColorMorphs(taxonomy_id=1, morph_name="Rainbow", description="Multi-colored polyps", rarity="Rare", source="Fiji"),
                ColorMorphs(taxonomy_id=3, morph_name="Superman", description="Red and blue coloration", rarity="Ultra", source="Indonesia"),
                ColorMorphs(taxonomy_id=6, morph_name="Gold Torch", description="Golden yellow tips", rarity="Uncommon", source="Australia"),
                ColorMorphs(taxonomy_id=14, morph_name="Fire and Ice", description="Orange and blue polyps", rarity="Rare", source="Caribbean")
            ]
            
            for morph in color_morphs:
                db.session.add(morph)
            
            # Seed Products
            products = [
                Products(name="Red Sea Reef Foundation A (Ca/Sr)", uses="+Ca", total_volume=500.0, current_avail=500.0, dry_refill=0.0),
                Products(name="Red Sea Reef Foundation B (Alk)", uses="+Alk", total_volume=500.0, current_avail=500.0, dry_refill=0.0),
                Products(name="Red Sea Reef Foundation C (Mg)", uses="+Mg", total_volume=500.0, current_avail=500.0, dry_refill=0.0),
                Products(name="Brightwell Aquatics NeoNitro", uses="-NO3", total_volume=250.0, current_avail=250.0, dry_refill=0.0),
                Products(name="Red Sea NO3:PO4-X", uses="-NO3/-PO4", total_volume=500.0, current_avail=500.0, dry_refill=0.0),
                Products(name="All-For-Reef", uses="+Ca/+Alk/+Mg", total_volume=5000.0, current_avail=5000.0, dry_refill=0.0),
                Products(name="Coral Amino", uses="Nutrition", total_volume=500.0, current_avail=500.0, dry_refill=0.0),
                Products(name="Acro Power", uses="Nutrition", total_volume=500.0, current_avail=500.0, dry_refill=0.0)
            ]
            
            for product in products:
                db.session.add(product)
            
            # Commit products to get IDs
            db.session.commit()
            
            # Seed Care Requirements
            care_reqs = [
                CareReqs(genus="Acropora", temperature=Decimal('25.5'), salinity=Decimal('1.025'), 
                        pH=Decimal('8.2'), alkalinity=Decimal('8.5'), calcium=420, magnesium=1350, 
                        par=300, flow="High", notes="Requires high light and flow"),
                CareReqs(genus="Euphyllia", temperature=Decimal('25.0'), salinity=Decimal('1.025'), 
                        pH=Decimal('8.1'), alkalinity=Decimal('8.0'), calcium=400, magnesium=1300, 
                        par=150, flow="Moderate", notes="Moderate requirements, aggressive when feeding"),
                CareReqs(genus="Montipora", temperature=Decimal('25.5'), salinity=Decimal('1.025'), 
                        pH=Decimal('8.2'), alkalinity=Decimal('8.5'), calcium=420, magnesium=1350, 
                        par=250, flow="Moderate", notes="Hardy SPS, good beginner coral")
            ]
            
            for care_req in care_reqs:
                db.session.add(care_req)
            
            # Seed Test Results (sample data for main tank)
            test_results = [
                TestResults(test_date=date(2025, 5, 20), test_time=time(10, 0), 
                           alk=8.2, po4_ppm=0.05, po4_ppb=50, no3_ppm=5, cal=420, mg=1350.0, sg=1.025, tank_id=1),
                TestResults(test_date=date(2025, 5, 22), test_time=time(10, 0), 
                           alk=8.0, po4_ppm=0.06, po4_ppb=60, no3_ppm=8, cal=415, mg=1340.0, sg=1.025, tank_id=1),
                TestResults(test_date=date(2025, 5, 24), test_time=time(10, 0), 
                           alk=8.3, po4_ppm=0.04, po4_ppb=40, no3_ppm=3, cal=425, mg=1360.0, sg=1.025, tank_id=1)
            ]
            
            for test in test_results:
                db.session.add(test)
            
            # Seed Dosing Schedules for main tank
            dosing_schedules = [
                DSchedule(trigger_interval=86400, suspended=False, amount=5.0, tank_id=1, product_id=2),  # Daily Alk dosing
                DSchedule(trigger_interval=86400, suspended=False, amount=5.0, tank_id=1, product_id=1),  # Daily Ca dosing
                DSchedule(trigger_interval=172800, suspended=False, amount=2.0, tank_id=1, product_id=3), # Bi-daily Mg dosing
                DSchedule(trigger_interval=259200, suspended=True, amount=1.0, tank_id=1, product_id=5),  # Tri-daily NO3:PO4-X (suspended)
            ]
            
            for schedule in dosing_schedules:
                db.session.add(schedule)
            
            # Commit schedules to get IDs
            db.session.commit()
            
            # Seed some sample corals
            sample_corals = [
                Coral(coral_name="Blue Tip Staghorn", date_acquired=date(2025, 4, 15), par=300, 
                     flow="High", placement="Top", current_size="3 inches", health_status="Healthy", 
                     frag_colony="Colony", unique_id="SPS001", notes="Growing well, shows polyp extension",
                     taxonomy_id=1, tank_id=1, vendors_id=1, color_morphs_id=1),
                Coral(coral_name="Gold Torch", date_acquired=date(2025, 3, 20), par=150, 
                     flow="Medium", placement="Middle", current_size="5 heads", health_status="Healthy", 
                     frag_colony="Colony", unique_id="LPS001", notes="Beautiful coloration, feeds well",
                     taxonomy_id=7, tank_id=1, vendors_id=2, color_morphs_id=4),
                Coral(coral_name="Superman Monti", date_acquired=date(2025, 5, 1), par=250, 
                     flow="Medium", placement="Middle", current_size="2 inches", health_status="New", 
                     frag_colony="Frag", unique_id="SPS002", notes="Recently acquired, acclimating well",
                     taxonomy_id=3, tank_id=1, vendors_id=3, color_morphs_id=3)
            ]
            
            for coral in sample_corals:
                db.session.add(coral)
            
            # Seed Alkalinity Model for main tank
            alk_model = AlkalinityDoseModel(
                tank_id=1, product_id=2, slope=1.2, intercept=0.5, weight_decay=0.9,
                r2_score=0.85, notes="Initial model based on system characteristics"
            )
            db.session.add(alk_model)
            
            # Final commit
            db.session.commit()
            logger.info("Database seeding completed successfully")
            
            # Log summary
            logger.info(f"Created {len(tanks)} tanks")
            logger.info(f"Created {len(vendors)} vendors")
            logger.info(f"Created {len(taxonomies)} taxonomy entries")
            logger.info(f"Created {len(color_morphs)} color morphs")
            logger.info(f"Created {len(products)} products")
            logger.info(f"Created {len(care_reqs)} care requirement entries")
            logger.info(f"Created {len(test_results)} test results")
            logger.info(f"Created {len(dosing_schedules)} dosing schedules")
            logger.info(f"Created {len(sample_corals)} sample corals")
            logger.info("Created 1 alkalinity model")
            
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    logger.info("Starting database initialization...")
    init_database()
    logger.info("Database initialization completed!")