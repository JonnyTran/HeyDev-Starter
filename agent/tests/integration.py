"""
Integration tests for the DevRel publisher agent.
"""

import unittest
from unittest.mock import patch, MagicMock
from sample_agent.agent import DevRelAgentState, DevRelPublisherFlow

class TestDevRelPublisherFlow(unittest.TestCase):
    """Test cases for the DevRel publisher flow."""

    def test_end_to_end_flow(self):
        """Test the entire flow from repo URL to database save"""
        # Setup initial state
        state = DevRelAgentState()
        state.repo_url = "https://github.com/owner/repo"
        state.start_date = "2023-01-01"
        
        # Mock the GitHub API responses
        with patch('sample_agent.agent.github_api_request', new=MagicMock()) as mock_github:
            # Mock commits response
            mock_github.return_value = [{"sha": "abc123", "commit": {"message": "Fix bug", "author": {"date": "2023-02-01"}}}]
            
            # Test analyze repository
            analyze_repository_node = DevRelPublisherFlow().analyze_repository
            with patch('sample_agent.agent.copilotkit_emit_state', new=MagicMock()):
                next_node = analyze_repository_node(state)
            
            self.assertEqual(next_node, "generate_topics")
            self.assertTrue(len(state.commits) > 0)
            # Since we mocked the API, we'll have empty lists for these
            state.pull_requests = [{"number": 42, "title": "Add feature", "state": "closed", "created_at": "2023-02-05"}]
            state.issues = [{"number": 7, "title": "Fix bug", "state": "closed", "created_at": "2023-02-02"}]
            state.docs_changes = [{"commit": "abc123", "doc_files": ["README.md"]}]
        
        # Test topic generation with mocked completion
        with patch('sample_agent.agent.copilotkit_stream', new=MagicMock()) as mock_stream:
            # Mock the AI response
            mock_message = MagicMock()
            mock_message.get.return_value = [{
                "function": {
                    "name": "generate_topic",
                    "arguments": '{"title": "New Feature X", "description": "Overview of the new X feature", "source_type": "pull_request", "source_id": "42", "content_types": ["blog_post", "social_media"]}'
                }
            }]
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=mock_message)]
            mock_stream.return_value = mock_response
            
            # Mock the other required functions
            with patch('sample_agent.agent.copilotkit_predict_state', new=MagicMock()):
                generate_topics_node = DevRelPublisherFlow().generate_topics
                next_node = generate_topics_node(state)
            
            self.assertEqual(next_node, "user_selects_topic")
            self.assertTrue(len(state.topics) > 0)
        
        # Simulate user selection
        state.selected_topic = state.topics[0]
        
        # Test content generation with mocked completion
        with patch('sample_agent.agent.copilotkit_stream', new=MagicMock()) as mock_stream:
            # Mock the AI response
            mock_message = MagicMock()
            mock_message.get.return_value = [{
                "function": {
                    "name": "write_content",
                    "arguments": '{"content": "This is a test blog post", "title": "New Feature X Launch", "summary": "Learn about our newest feature"}'
                }
            }]
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=mock_message)]
            mock_stream.return_value = mock_response
            
            # Mock the other required functions
            with patch('sample_agent.agent.copilotkit_predict_state', new=MagicMock()):
                generate_content_node = DevRelPublisherFlow().generate_content_drafts
                next_node = generate_content_node(state)
            
            self.assertEqual(next_node, "user_edits_content")
            self.assertTrue(len(state.content_record["content"]) > 0)
        
        # Simulate user editing
        state.content_drafts["blog_post"] = "Edited content"
        state.content_record["content"] = "Edited content"
        state.copilotkit = MagicMock()
        state.copilotkit.metadata = {"confirmed": True}
        
        # Test saving to database with mocked DB functions
        with patch('sample_agent.db.insert_content', return_value=1) as mock_db:
            # Mock the emit state function
            with patch('sample_agent.agent.copilotkit_emit_state', new=MagicMock()):
                save_to_db_node = DevRelPublisherFlow().save_to_database
                next_node = save_to_db_node(state)
            
            self.assertEqual(next_node, "flow_complete")
            self.assertEqual(state.content_record["content"], "Edited content")
            mock_db.assert_called_once()

if __name__ == "__main__":
    unittest.main()