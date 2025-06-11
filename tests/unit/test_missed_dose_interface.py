import pytest
from datetime import datetime, timedelta
from app import app, db
from modules.models import Tank, TankSystem, Products, DSchedule, MissedDoseRequest, MissedDoseHandlingEnum

class TestMissedDoseInterface:
    """Test suite for missed dose interface functionality"""

    @pytest.fixture(autouse=True)
    def setup_test_data(self):
        """Setup test data for missed dose interface testing"""
        with app.app_context():
            # Create test tank
            self.test_tank = Tank(name="test-tank-missed-dose-interface")
            db.session.add(self.test_tank)
            db.session.commit()
            
            # Create test product
            self.test_product = Products(
                name="Test Product Interface",
                current_avail=100.0,
                total_volume=500.0
            )
            db.session.add(self.test_product)
            
            # Create test schedule with manual approval
            self.test_schedule = DSchedule(
                tank_id=self.test_tank.id,
                product_id=None,  # Will be set after product is committed
                amount=5.0,
                trigger_interval=86400,  # 24 hours
                missed_dose_handling=MissedDoseHandlingEnum.manual_approval,
                missed_dose_grace_period_hours=24
            )
            db.session.commit()
            
            # Update schedule with product_id
            self.test_schedule.product_id = self.test_product.id
            db.session.commit()

            # Set system context for testing
            from modules.system_context import set_system_id_for_testing
            # Determine system_id from tank's system or fallback to existing system
            if self.test_tank.tank_system_id:
                test_system_id = self.test_tank.tank_system_id
            else:
                existing_systems = TankSystem.query.limit(1).all()
                test_system_id = existing_systems[0].id if existing_systems else 1
            set_system_id_for_testing(test_system_id)
            
            yield
            
            # Cleanup
            db.session.query(MissedDoseRequest).filter_by(schedule_id=self.test_schedule.id).delete()
            db.session.query(DSchedule).filter_by(tank_id=self.test_tank.id).delete()
            db.session.delete(self.test_product)
            db.session.delete(self.test_tank)
            db.session.commit()

    def test_missed_dose_dashboard_loads(self):
        """Test that the missed dose dashboard loads correctly"""
        with app.app_context():
            with app.test_client() as client:
                response = client.get('/missed-dose/dashboard')
                assert response.status_code == 200
                
                html = response.get_data(as_text=True)
                
                # Check for new button text instead of old
                assert 'Dose' in html
                assert 'Skip' in html
                
                # Check that old button text is not present
                assert 'Approve' not in html
                assert 'Reject' not in html
                
                # Check for proper icons
                assert 'fa-syringe' in html  # Dose button icon
                assert 'fa-forward' in html  # Skip button icon

    def test_missed_dose_interface_with_pending_request(self):
        """Test missed dose interface when there are pending requests"""
        with app.app_context():
            # Create a missed dose request
            missed_dose_time = datetime.now() - timedelta(hours=2)
            detected_time = datetime.now() - timedelta(hours=1)
            
            missed_dose_request = MissedDoseRequest(
                schedule_id=self.test_schedule.id,
                missed_dose_time=missed_dose_time,
                detected_time=detected_time,
                hours_missed=2.0,
                status='pending'
            )
            db.session.add(missed_dose_request)
            db.session.commit()
            
            with app.test_client() as client:
                response = client.get('/missed-dose/dashboard')
                assert response.status_code == 200
                
                html = response.get_data(as_text=True)
                
                # Check that the pending request section is shown
                assert 'Missed Doses Requiring Action' in html
                
                # Check for the new button classes
                assert 'dose-btn' in html
                assert 'skip-btn' in html
                
                # Check for the test product name
                assert self.test_product.name in html
                
                # Check for dose information
                assert str(self.test_schedule.amount) in html

    def test_dose_action_api_call(self):
        """Test that dosing action calls the correct API endpoint"""
        with app.app_context():
            # Create a missed dose request
            missed_dose_request = MissedDoseRequest(
                schedule_id=self.test_schedule.id,
                missed_dose_time=datetime.now() - timedelta(hours=2),
                detected_time=datetime.now() - timedelta(hours=1),
                hours_missed=2.0,
                status='pending'
            )
            db.session.add(missed_dose_request)
            db.session.commit()
            
            with app.test_client() as client:
                # Test the dose action (which uses the approve endpoint)
                response = client.post('/api/v1/missed-dose/approve', 
                                     json={
                                         'request_id': missed_dose_request.id,
                                         'notes': 'Test dose action'
                                     })
                
                assert response.status_code == 200
                data = response.get_json()
                assert data['success'] is True
                assert 'scheduled' in data['message'].lower()

    def test_skip_action_api_call(self):
        """Test that skip action calls the correct API endpoint"""
        with app.app_context():
            # Create a missed dose request
            missed_dose_request = MissedDoseRequest(
                schedule_id=self.test_schedule.id,
                missed_dose_time=datetime.now() - timedelta(hours=2),
                detected_time=datetime.now() - timedelta(hours=1),
                hours_missed=2.0,
                status='pending'
            )
            db.session.add(missed_dose_request)
            db.session.commit()
            
            with app.test_client() as client:
                # Test the skip action (which uses the reject endpoint)
                response = client.post('/api/v1/missed-dose/reject', 
                                     json={
                                         'request_id': missed_dose_request.id,
                                         'notes': 'Test skip action'
                                     })
                
                assert response.status_code == 200
                data = response.get_json()
                assert data['success'] is True

    def test_modal_button_text_updates(self):
        """Test that modal buttons update correctly based on action"""
        with app.app_context():
            with app.test_client() as client:
                response = client.get('/missed-dose/dashboard')
                html = response.get_data(as_text=True)
                
                # Check that the JavaScript includes the correct button updates
                assert 'Dose Now' in html
                assert 'Skip Dose' in html
                assert 'btn-success' in html  # For dose button
                assert 'btn-warning' in html  # For skip button
