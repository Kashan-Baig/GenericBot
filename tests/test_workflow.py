import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.storage.conversation_store import store

client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_store():
    # Clear conversation store before each test to guarantee isolation
    store.clear_all()

def test_start_conversation():
    response = client.post("/chat", json={
        "conversation_id": "session1",
        "flow_id": "demo_flow",
        "message": "Hi"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["conversation_id"] == "session1"
    assert "Welcome to our business!" in data["response"]
    assert "What would you like to do?" in data["response"]
    assert "1. Service A" in data["response"]
    assert "2. Service B" in data["response"]
    assert data["current_node"] == "choose_service"
    assert data["status"] == "waiting_for_input"

def test_select_service_b_and_end():
    # Start
    res1 = client.post("/chat", json={
        "conversation_id": "session_b",
        "flow_id": "demo_flow",
        "message": "Hi"
    })
    assert res1.json()["current_node"] == "choose_service"
    
    # Select Service B (using option index string "2")
    res2 = client.post("/chat", json={
        "conversation_id": "session_b",
        "message": "2"
    })
    assert res2.status_code == 200
    data2 = res2.json()
    assert "Service B provides dental hygiene services." in data2["response"]
    assert "Thank you for chatting with us. Goodbye!" in data2["response"]
    assert data2["current_node"] == "END"
    assert data2["status"] == "completed"

def test_select_service_a_input_name_and_condition_kashan():
    # Start
    client.post("/chat", json={"conversation_id": "session_a", "flow_id": "demo_flow", "message": "Hi"})
    
    # Select Service A by typing its label "Service A"
    res1 = client.post("/chat", json={"conversation_id": "session_a", "message": "Service A"})
    data1 = res1.json()
    assert "Service A provides professional IT consulting." in data1["response"]
    assert "What is your name?" in data1["response"]
    assert data1["current_node"] == "ask_name"
    assert data1["status"] == "waiting_for_input"
    
    # Input Name "Kashan" (Conditions match)
    res2 = client.post("/chat", json={"conversation_id": "session_a", "message": "Kashan"})
    data2 = res2.json()
    assert data2["variables"].get("customer_name") == "Kashan"
    assert "Welcome back, Kashan! We have prepared a special discount for you." in data2["response"]
    assert "Thank you for chatting with us. Goodbye!" in data2["response"]
    assert data2["current_node"] == "END"
    assert data2["status"] == "completed"

def test_select_service_a_input_name_and_condition_generic():
    # Start
    client.post("/chat", json={"conversation_id": "session_a_other", "flow_id": "demo_flow", "message": "Hi"})
    
    # Select Service A
    client.post("/chat", json={"conversation_id": "session_a_other", "message": "Service A"})
    
    # Input Name "Alice" (Conditions do not match, trigger fallback branch)
    res = client.post("/chat", json={"conversation_id": "session_a_other", "message": "Alice"})
    data = res.json()
    assert data["variables"].get("customer_name") == "Alice"
    assert "Nice to meet you! Thank you for sharing your name." in data["response"]
    assert "Goodbye!" in data["response"]
    assert data["current_node"] == "END"
    assert data["status"] == "completed"

def test_invalid_button_input():
    # Start
    client.post("/chat", json={"conversation_id": "invalid_btn", "flow_id": "demo_flow", "message": "Hi"})
    
    # Send invalid button option
    res = client.post("/chat", json={"conversation_id": "invalid_btn", "message": "Invalid Choice"})
    data = res.json()
    assert "Invalid selection. Please choose one of the options:" in data["response"]
    assert data["current_node"] == "choose_service"
    assert data["status"] == "waiting_for_input"
    
    # Verify we can recover and complete the flow by sending a correct choice
    res2 = client.post("/chat", json={"conversation_id": "invalid_btn", "message": "2"})
    assert res2.json()["status"] == "completed"
    assert "Service B provides dental" in res2.json()["response"]

def test_multiple_conversations():
    # Start user 1
    client.post("/chat", json={"conversation_id": "user1", "flow_id": "demo_flow", "message": "Hi"})
    
    # Start user 2
    client.post("/chat", json={"conversation_id": "user2", "flow_id": "demo_flow", "message": "Hi"})
    
    # Select Service A for user 1
    res1 = client.post("/chat", json={"conversation_id": "user1", "message": "1"})
    assert "What is your name?" in res1.json()["response"]
    
    # Select Service B for user 2
    res2 = client.post("/chat", json={"conversation_id": "user2", "message": "2"})
    assert "dental hygiene" in res2.json()["response"]
    assert res2.json()["status"] == "completed"
    
    # Validate user 1's state is completely unaffected
    state1 = store.get_state("user1")
    assert state1["current_node"] == "ask_name"
    assert state1["status"] == "waiting_for_input"
