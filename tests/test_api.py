"""
Tests for the Mergington High School Activities API
"""

import pytest
from fastapi.testclient import TestClient
from src.app import app, activities
import copy


@pytest.fixture
def client():
    """Create a test client for the FastAPI app"""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_activities():
    """Reset activities to initial state before each test"""
    # Store original activities
    original_activities = copy.deepcopy(activities)
    
    yield
    
    # Restore original activities after test
    activities.clear()
    activities.update(original_activities)


class TestRootEndpoint:
    """Tests for the root endpoint"""
    
    def test_root_redirects_to_index(self, client):
        """Test that root redirects to static index.html"""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/static/index.html"


class TestGetActivities:
    """Tests for GET /activities endpoint"""
    
    def test_get_activities_returns_all_activities(self, client):
        """Test that GET /activities returns all activities"""
        response = client.get("/activities")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, dict)
        assert "Chess Club" in data
        assert "Basketball" in data
        assert "Tennis" in data
        
    def test_get_activities_has_correct_structure(self, client):
        """Test that activities have the correct structure"""
        response = client.get("/activities")
        data = response.json()
        
        chess_club = data["Chess Club"]
        assert "description" in chess_club
        assert "schedule" in chess_club
        assert "max_participants" in chess_club
        assert "participants" in chess_club
        assert isinstance(chess_club["participants"], list)


class TestSignupForActivity:
    """Tests for POST /activities/{activity_name}/signup endpoint"""
    
    def test_signup_for_existing_activity_success(self, client):
        """Test successful signup for an existing activity"""
        response = client.post(
            "/activities/Chess%20Club/signup?email=newstudent@mergington.edu"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert "newstudent@mergington.edu" in data["message"]
        assert "Chess Club" in data["message"]
        
        # Verify student was added to participants
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert "newstudent@mergington.edu" in activities_data["Chess Club"]["participants"]
    
    def test_signup_for_nonexistent_activity(self, client):
        """Test signup for a non-existent activity returns 404"""
        response = client.post(
            "/activities/Nonexistent%20Activity/signup?email=student@mergington.edu"
        )
        assert response.status_code == 404
        assert "Activity not found" in response.json()["detail"]
    
    def test_signup_duplicate_student(self, client):
        """Test that a student cannot sign up for the same activity twice"""
        email = "duplicate@mergington.edu"
        
        # First signup should succeed
        response1 = client.post(
            f"/activities/Basketball/signup?email={email}"
        )
        assert response1.status_code == 200
        
        # Second signup should fail
        response2 = client.post(
            f"/activities/Basketball/signup?email={email}"
        )
        assert response2.status_code == 400
        assert "already signed up" in response2.json()["detail"]
    
    def test_signup_updates_participants_list(self, client):
        """Test that signup properly updates the participants list"""
        initial_response = client.get("/activities")
        initial_count = len(initial_response.json()["Basketball"]["participants"])
        
        client.post("/activities/Basketball/signup?email=newplayer@mergington.edu")
        
        final_response = client.get("/activities")
        final_count = len(final_response.json()["Basketball"]["participants"])
        
        assert final_count == initial_count + 1


class TestUnregisterFromActivity:
    """Tests for DELETE /activities/{activity_name}/unregister endpoint"""
    
    def test_unregister_existing_participant_success(self, client):
        """Test successful unregistration of an existing participant"""
        # First sign up a student
        client.post("/activities/Tennis/signup?email=temp@mergington.edu")
        
        # Then unregister them
        response = client.delete(
            "/activities/Tennis/unregister?email=temp@mergington.edu"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert "temp@mergington.edu" in data["message"]
        assert "Tennis" in data["message"]
        
        # Verify student was removed from participants
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert "temp@mergington.edu" not in activities_data["Tennis"]["participants"]
    
    def test_unregister_from_nonexistent_activity(self, client):
        """Test unregister from a non-existent activity returns 404"""
        response = client.delete(
            "/activities/Fake%20Activity/unregister?email=student@mergington.edu"
        )
        assert response.status_code == 404
        assert "Activity not found" in response.json()["detail"]
    
    def test_unregister_non_registered_student(self, client):
        """Test unregistering a student who is not registered returns 400"""
        response = client.delete(
            "/activities/Chess%20Club/unregister?email=notregistered@mergington.edu"
        )
        assert response.status_code == 400
        assert "not registered" in response.json()["detail"]
    
    def test_unregister_updates_participants_list(self, client):
        """Test that unregister properly updates the participants list"""
        # Get initial count
        initial_response = client.get("/activities")
        initial_participants = initial_response.json()["Chess Club"]["participants"]
        initial_count = len(initial_participants)
        
        # Unregister an existing participant
        email_to_remove = initial_participants[0]
        client.delete(f"/activities/Chess%20Club/unregister?email={email_to_remove}")
        
        # Check final count
        final_response = client.get("/activities")
        final_count = len(final_response.json()["Chess Club"]["participants"])
        
        assert final_count == initial_count - 1
    
    def test_unregister_removes_correct_student(self, client):
        """Test that unregister removes the correct student"""
        # Add two students
        client.post("/activities/Drama%20Club/signup?email=student1@mergington.edu")
        client.post("/activities/Drama%20Club/signup?email=student2@mergington.edu")
        
        # Unregister one
        client.delete("/activities/Drama%20Club/unregister?email=student1@mergington.edu")
        
        # Verify correct student was removed
        response = client.get("/activities")
        participants = response.json()["Drama Club"]["participants"]
        assert "student1@mergington.edu" not in participants
        assert "student2@mergington.edu" in participants


class TestEndToEndWorkflows:
    """End-to-end workflow tests"""
    
    def test_complete_signup_and_unregister_workflow(self, client):
        """Test complete workflow: signup, verify, unregister, verify"""
        email = "workflow@mergington.edu"
        activity = "Programming Class"
        
        # Get initial state
        initial_response = client.get("/activities")
        initial_participants = initial_response.json()[activity]["participants"]
        assert email not in initial_participants
        
        # Signup
        signup_response = client.post(f"/activities/{activity.replace(' ', '%20')}/signup?email={email}")
        assert signup_response.status_code == 200
        
        # Verify signup
        after_signup = client.get("/activities")
        assert email in after_signup.json()[activity]["participants"]
        
        # Unregister
        unregister_response = client.delete(f"/activities/{activity.replace(' ', '%20')}/unregister?email={email}")
        assert unregister_response.status_code == 200
        
        # Verify unregister
        after_unregister = client.get("/activities")
        assert email not in after_unregister.json()[activity]["participants"]
    
    def test_multiple_students_same_activity(self, client):
        """Test multiple students can sign up for the same activity"""
        activity = "Science Olympiad"
        emails = ["student1@mergington.edu", "student2@mergington.edu", "student3@mergington.edu"]
        
        # Sign up all students
        for email in emails:
            response = client.post(f"/activities/{activity.replace(' ', '%20')}/signup?email={email}")
            assert response.status_code == 200
        
        # Verify all students are registered
        response = client.get("/activities")
        participants = response.json()[activity]["participants"]
        for email in emails:
            assert email in participants
