import pytest
import json
from datetime import datetime, date, time
from app import app, db
from modules.models import Tank, TestResults

class TestHomeRoutes:
    """Test suite for home page routes and functionality"""

    @pytest.fixture(autouse=True)
    def setup_test_data(self):
        """Setup test data for each test"""
        with app.app_context():
            # Create a test tank
            self.test_tank = Tank(name="test-tank-home")
            db.session.add(self.test_tank)
            db.session.commit()
            
            # Create some test data
            test_data = [
                TestResults(
                    tank_id=self.test_tank.id,
                    test_date=date(2024, 1, 1),
                    test_time=time(10, 0),
                    alk=8.5,
                    cal=420,
                    mg=1300.0,
                    po4_ppm=0.05,
                    no3_ppm=5,
                    sg=1.025
                ),
                TestResults(
                    tank_id=self.test_tank.id,
                    test_date=date(2024, 1, 2),
                    test_time=time(10, 0),
                    alk=8.2,
                    cal=415,
                    mg=1290.0,
                    po4_ppm=0.04,
                    no3_ppm=4,
                    sg=1.024
                ),
                TestResults(
                    tank_id=self.test_tank.id,
                    test_date=date(2024, 1, 5),
                    test_time=time(10, 0),
                    alk=8.8,
                    cal=430,
                    mg=1320.0,
                    po4_ppm=0.06,
                    no3_ppm=6,
                    sg=1.026
                )
            ]
            
            for test in test_data:
                db.session.add(test)
            db.session.commit()
            
            yield
            
            # Cleanup
            TestResults.query.filter_by(tank_id=self.test_tank.id).delete()
            db.session.delete(self.test_tank)
            db.session.commit()

    def test_home_route_basic(self):
        """Test that home route returns 200 and contains expected content"""
        with app.test_client() as client:
            response = client.get("/")
            assert response.status_code == 200
            
            # Check that essential elements are present
            html_content = response.get_data(as_text=True)
            assert "Tank Dashboard" in html_content
            assert "Welcome to your reef tank management system" in html_content
            assert "Test Results Chart" in html_content
            assert "Quick Actions" in html_content

    def test_home_route_card_structure(self):
        """Test that home page contains all expected cards"""
        with app.test_client() as client:
            response = client.get("/")
            html_content = response.get_data(as_text=True)
            
            # Check for all expected cards
            assert "📊 Test Results Chart" in html_content
            assert "⚡ Quick Actions" in html_content
            assert "🔧 System" in html_content
            assert "🤖 AI Models" in html_content
            assert "💾 Data" in html_content

    def test_home_route_links(self):
        """Test that home page contains expected navigation links"""
        with app.test_client() as client:
            response = client.get("/")
            html_content = response.get_data(as_text=True)
            
            # Check for important links
            assert 'href="/chart"' in html_content
            assert 'href="/test/add"' in html_content
            assert 'href="/test"' in html_content
            assert 'href="/coral/add"' in html_content
            assert 'href="/metrics"' in html_content
            assert 'href="/models/view"' in html_content

    def test_chart_route_basic(self):
        """Test that chart route returns 200 when tank is selected"""
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['tank_id'] = self.test_tank.id
            
            response = client.get("/chart")
            assert response.status_code == 200
            
            html_content = response.get_data(as_text=True)
            assert "Test Results Chart" in html_content
            assert "Interactive water parameter visualization" in html_content

    def test_chart_route_no_tank_selected(self):
        """Test that chart route redirects when no tank is selected"""
        with app.test_client() as client:
            response = client.get("/chart")
            assert response.status_code == 302  # Redirect
            assert response.location.endswith("/")

    def test_chart_route_structure(self):
        """Test that chart page contains expected elements"""
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['tank_id'] = self.test_tank.id
            
            response = client.get("/chart")
            html_content = response.get_data(as_text=True)
            
            # Check for chart structure elements
            assert "chart-layout" in html_content
            assert "controls-left" in html_content
            assert "chart-main" in html_content
            assert "controls-right" in html_content
            assert "testResultsChart" in html_content

    def test_chart_route_parameters(self):
        """Test that chart page contains parameter controls"""
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['tank_id'] = self.test_tank.id
            
            response = client.get("/chart")
            html_content = response.get_data(as_text=True)
            
            # Check for parameter checkboxes
            assert 'id="show-alk"' in html_content
            assert 'id="show-cal"' in html_content
            assert 'id="show-mg"' in html_content
            assert 'id="show-po4"' in html_content
            assert 'id="show-no3"' in html_content
            assert 'id="show-sg"' in html_content
            
            # Check for interpolated parameter checkboxes
            assert 'id="show-alk-interp"' in html_content
            assert 'id="show-cal-interp"' in html_content

    def test_api_test_results_data_with_tank(self):
        """Test API endpoint returns test data when tank is selected"""
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['tank_id'] = self.test_tank.id
            response = client.get("/api/v1/home/test-results-data")
            assert response.status_code == 200
            data = json.loads(response.get_data(as_text=True))
            assert "labels" in data
            assert "datasets" in data
            assert len(data["labels"]) > 0
            assert len(data["datasets"]) > 0

    def test_api_test_results_data_no_tank(self):
        """Test API endpoint returns error when no tank is selected"""
        with app.test_client() as client:
            response = client.get("/api/v1/home/test-results-data")
            assert response.status_code == 400
            data = json.loads(response.get_data(as_text=True))
            assert "error" in data
            assert data["error"] == "No tank selected"

    def test_api_test_results_data_structure(self):
        """Test API endpoint returns correctly structured data"""
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['tank_id'] = self.test_tank.id
            response = client.get("/api/v1/home/test-results-data")
            data = json.loads(response.get_data(as_text=True))
            # Check structure
            assert isinstance(data["labels"], list)
            assert isinstance(data["datasets"], list)
            # Should have datasets for both original and interpolated data
            # 6 parameters × 2 (original + interpolated) = 12 datasets
            assert len(data["datasets"]) == 12
            # Check dataset structure
            for dataset in data["datasets"]:
                assert "label" in dataset
                assert "data" in dataset
                assert "borderColor" in dataset
                assert isinstance(dataset["data"], list)

    def test_api_test_results_interpolation(self):
        """Test that API includes interpolated data correctly"""
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['tank_id'] = self.test_tank.id
            response = client.get("/api/v1/home/test-results-data")
            data = json.loads(response.get_data(as_text=True))
            # Find interpolated datasets (should have "(Interpolated)" in label)
            interpolated_datasets = [d for d in data["datasets"] if "(Interpolated)" in d["label"]]
            assert len(interpolated_datasets) == 6  # One for each parameter
            # Check that interpolated datasets have dashed line style
            for dataset in interpolated_datasets:
                assert dataset.get("borderDash") == [5, 5]

    def test_set_tank_route(self):
        """Test tank selection route"""
        with app.test_client() as client:
            response = client.post("/set_tank", data={"tank_id": self.test_tank.id})
            assert response.status_code == 302  # Redirect
            
            # Check that session was updated
            with client.session_transaction() as sess:
                assert sess.get('tank_id') == self.test_tank.id

    def test_health_check_route(self):
        """Test health check endpoint"""
        with app.test_client() as client:
            response = client.get("/health")
            assert response.status_code == 200
            
            data = json.loads(response.get_data(as_text=True))
            assert data["status"] in ["healthy", "degraded"]
            assert "database" in data
            assert "timestamp" in data
