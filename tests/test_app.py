def test_index_returns_html(client):
	response = client.get("/")
	assert response.status_code == 200
	assert "GitPulse" in response.text
	assert "text/html" in response.headers["content-type"]
