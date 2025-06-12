import unittest
from unittest.mock import patch, MagicMock, call
import sys
import os
import json

# Adjust the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from TradingAgents.tradingagents.agents.analysts.social_media_analyst import create_social_media_analyst
# Import SentimentAnalyzer for type hinting or instance checks if needed, though it will be mocked.
from TradingAgents.tradingagents.predictive_models.sentiment_analyzer import SentimentAnalyzer
from langchain_core.messages import ToolMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate

# Helper function to create sample Reddit tool output
def create_sample_reddit_tool_output(posts_data):
    """Creates a JSON string similar to what get_reddit_stock_info might return."""
    return json.dumps(posts_data)

class TestSocialMediaAnalystIntegration(unittest.TestCase):
    """
    Test cases for the SocialMediaAnalyst node, focusing on SentimentAnalyzer integration.
    """

    def setUp(self):
        """
        Set up mock LLM, mock toolkit, and the social_media_analyst_node.
        """
        self.mock_llm = MagicMock()
        # Mock the behavior of the LLM when tools are bound and invoked.
        # This mock needs to simulate the chain: prompt | llm.bind_tools(tools)
        # For simplicity, we'll have the llm itself return an AIMessage when invoked.
        self.mock_llm_invoked_response = AIMessage(content="Mocked LLM sentiment report.")
        self.mock_llm.bind_tools.return_value = self.mock_llm # chain LLM after binding
        self.mock_llm.invoke.return_value = self.mock_llm_invoked_response


        self.mock_toolkit = MagicMock()
        self.mock_toolkit.config = {"online_tools": False} # Use offline tools by default (get_reddit_stock_info)

        self.mock_get_reddit_stock_info = MagicMock(name="get_reddit_stock_info")
        self.mock_get_reddit_stock_info.name = "get_reddit_stock_info" # Tool name is important
        self.mock_toolkit.get_reddit_stock_info = self.mock_get_reddit_stock_info

        # This is the function that returns the node
        self.social_media_analyst_func = create_social_media_analyst(self.mock_llm, self.mock_toolkit)

    @patch('TradingAgents.tradingagents.agents.analysts.social_media_analyst.SentimentAnalyzer')
    def test_sentiment_analyzer_initialization_and_usage(self, MockedSentimentAnalyzer):
        """
        Test that SentimentAnalyzer is initialized and its predict_sentiment method is called.
        """
        mock_sentiment_instance = MockedSentimentAnalyzer.return_value
        mock_sentiment_instance.predict_sentiment.return_value = [
            {"text": "Test text", "sentiment_label": "positive", "sentiment_score": 0.9}
        ]

        sample_posts = [{"title": "Great news for Company X!", "selftext": "Stock is going up."}]
        tool_message_content = create_sample_reddit_tool_output(sample_posts)

        initial_state = {
            "trade_date": "2024-01-01",
            "company_of_interest": "CompanyX",
            "messages": [
                HumanMessage(content="Analyze CompanyX"),
                ToolMessage(content=tool_message_content, name="get_reddit_stock_info")
            ]
        }

        self.social_media_analyst_func(initial_state)

        MockedSentimentAnalyzer.assert_called_once_with(model_type='vader')
        mock_sentiment_instance.predict_sentiment.assert_called_once()
        # Check that it was called with the extracted texts
        # The texts are sorted list of unique texts
        expected_texts_for_sentiment = sorted(list(set(["Great news for Company X!", "Stock is going up."])))
        called_with_texts = mock_sentiment_instance.predict_sentiment.call_args[0][0]
        self.assertEqual(sorted(called_with_texts), expected_texts_for_sentiment)


    @patch('TradingAgents.tradingagents.agents.analysts.social_media_analyst.SentimentAnalyzer')
    def test_text_extraction_from_tool_message(self, MockedSentimentAnalyzer):
        """
        Test correct text extraction from various ToolMessage content structures.
        """
        mock_sentiment_instance = MockedSentimentAnalyzer.return_value
        mock_sentiment_instance.predict_sentiment.return_value = [] # Return value doesn't matter for this test

        posts1 = [{"title": "Title 1", "selftext": "Content 1"}]
        posts2 = [{"title": "Only title here", "content": None}] # Test None content
        posts3 = [{"content": "Only content here", "title": ""}] # Test empty title
        posts4 = [{"title": "Title 4", "selftext": "Selftext 4", "content": "Content 4 should be ignored if selftext exists"}]
        posts5 = "Just a string output, not JSON" # Non-JSON string
        posts6 = [{"random_key": "No title or content"}]

        tool_message1 = ToolMessage(content=create_sample_reddit_tool_output(posts1), name="get_reddit_stock_info")
        tool_message2 = ToolMessage(content=create_sample_reddit_tool_output(posts2), name="get_reddit_stock_info")
        tool_message3 = ToolMessage(content=create_sample_reddit_tool_output(posts3), name="get_reddit_stock_info")
        tool_message4 = ToolMessage(content=create_sample_reddit_tool_output(posts4), name="get_reddit_stock_info")
        tool_message5 = ToolMessage(content=posts5, name="get_reddit_stock_info")
        tool_message6 = ToolMessage(content=create_sample_reddit_tool_output(posts6), name="get_reddit_stock_info")


        initial_state_template = lambda msg: {
            "trade_date": "2024-01-01", "company_of_interest": "TestCo", "messages": [msg]
        }

        # Test case 1
        self.social_media_analyst_func(initial_state_template(tool_message1))
        mock_sentiment_instance.predict_sentiment.assert_called_with(sorted(["Title 1", "Content 1"]))

        # Test case 2
        self.social_media_analyst_func(initial_state_template(tool_message2))
        mock_sentiment_instance.predict_sentiment.assert_called_with(["Only title here"])

        # Test case 3
        self.social_media_analyst_func(initial_state_template(tool_message3))
        mock_sentiment_instance.predict_sentiment.assert_called_with(["Only content here"])

        # Test case 4 (content should be ignored due to selftext presence)
        self.social_media_analyst_func(initial_state_template(tool_message4))
        mock_sentiment_instance.predict_sentiment.assert_called_with(sorted(["Title 4", "Selftext 4"]))

        # Test case 5
        self.social_media_analyst_func(initial_state_template(tool_message5))
        mock_sentiment_instance.predict_sentiment.assert_called_with(["Just a string output, not JSON"])

        # Test case 6 (no relevant text)
        self.social_media_analyst_func(initial_state_template(tool_message6))
        # predict_sentiment might be called with an empty list if no text is extracted,
        # or the logic might just result in "No textual data extracted..." message.
        # The current implementation in social_media_analyst results in a HumanMessage "No textual data extracted..."
        # and predict_sentiment is not called if unique_texts is empty.
        # So, we check that it was *not* called again with non-empty list for this specific case if it was called before.
        # For a clean test, let's ensure it's about the *last* call or reset mock between specific sub-tests.
        # For simplicity, we assume it may be called with empty list from previous calls if not reset,
        # or we can check the appended message.
        # The `HumanMessage` with "No textual data extracted..." would be added.
        # For this test, we'll assert it's called with an empty list if that's the path.
        # Based on current social_media_analyst.py, if unique_texts is empty, predict_sentiment is NOT called.
        # The last call was with ["Just a string output, not JSON"]. So, it shouldn't be called again.
        # To make this test more isolated, one would typically reset the mock or check call_count.
        # Let's assume it's called with an empty list if that path is taken, or not called if no new texts.
        # The current code does: if unique_texts: self.analyzer.predict_sentiment(unique_texts)
        # So if no texts from posts6, it won't be called.
        # We check the last call was for posts5.
        self.assertEqual(mock_sentiment_instance.predict_sentiment.call_args[0][0], ["Just a string output, not JSON"])


    @patch('TradingAgents.tradingagents.agents.analysts.social_media_analyst.SentimentAnalyzer')
    def test_sentiment_data_added_to_llm_messages(self, MockedSentimentAnalyzer):
        """
        Test that formatted sentiment data is added as a HumanMessage to the LLM's input.
        """
        mock_sentiment_instance = MockedSentimentAnalyzer.return_value
        predefined_sentiment_data = [
            {"text": "Sample Text 1", "sentiment_label": "positive", "sentiment_score": 0.88},
            {"text": "Sample Text 2", "sentiment_label": "negative", "sentiment_score": -0.77}
        ]
        mock_sentiment_instance.predict_sentiment.return_value = predefined_sentiment_data

        sample_posts = [{"title": "Sample Text 1", "selftext": "Sample Text 2"}]
        tool_message = ToolMessage(content=create_sample_reddit_tool_output(sample_posts), name="get_reddit_stock_info")

        initial_state = {
            "trade_date": "2024-01-01", "company_of_interest": "TestCo",
            "messages": [HumanMessage(content="Initial prompt"), tool_message]
        }

        # Capture the arguments to llm.invoke
        # self.mock_llm.invoke = MagicMock(return_value=self.mock_llm_invoked_response)

        self.social_media_analyst_func(initial_state)

        # The llm.invoke is called with a dict where 'messages' is a key
        passed_to_llm_messages = self.mock_llm.invoke.call_args[0][0]["messages"]

        self.assertTrue(any(
            isinstance(msg, HumanMessage) and "Sentiment Analysis Results:" in msg.content
            for msg in passed_to_llm_messages
        ))

        sentiment_human_message_content = ""
        for msg in passed_to_llm_messages:
            if isinstance(msg, HumanMessage) and "Sentiment Analysis Results:" in msg.content:
                sentiment_human_message_content = msg.content
                break

        self.assertIn("- Text: \"Sample Text 1...\" -> Label: positive, Score: 0.88", sentiment_human_message_content)
        self.assertIn("- Text: \"Sample Text 2...\" -> Label: negative, Score: -0.77", sentiment_human_message_content)


    @patch('TradingAgents.tradingagents.agents.analysts.social_media_analyst.ChatPromptTemplate.from_messages')
    def test_llm_prompt_receives_sentiment_instructions(self, mock_from_messages):
        """
        Test that the system prompt for the LLM includes instructions on using sentiment data.
        """
        # We need to capture the system message passed to ChatPromptTemplate
        # The actual ChatPromptTemplate is created inside create_social_media_analyst
        # So, we re-instantiate the node function here to ensure the mock is in place for its creation.

        # This mock will capture the list of messages passed to from_messages
        mock_prompt_instance = MagicMock(spec=ChatPromptTemplate)
        mock_prompt_instance.partial.return_value = mock_prompt_instance #.partial returns self
        mock_from_messages.return_value = mock_prompt_instance

        # Re-create the node function so it uses the mocked ChatPromptTemplate
        node_func_with_mocked_prompt = create_social_media_analyst(self.mock_llm, self.mock_toolkit)

        initial_state = {"trade_date": "2024-01-01", "company_of_interest": "TestCo", "messages": []}
        node_func_with_mocked_prompt(initial_state) # Call the node to trigger prompt creation

        # Check the calls to from_messages. The system message is part of the first argument.
        # The system message itself is constructed earlier and then passed to .partial
        # We need to check the system_message variable inside create_social_media_analyst
        # This is hard to check directly without refactoring or more complex mocking of the prompt object.

        # Alternative: Check the `system_message` argument passed to `prompt.partial`
        # The prompt object itself is local to create_social_media_analyst.
        # Let's check the `system_message` argument to the final `prompt.partial` call.
        # The `ChatPromptTemplate` object is `mock_prompt_instance`.
        # We need to look at the calls to its `partial` method.

        system_message_call_args = None
        for call_item in mock_prompt_instance.partial.call_args_list:
            if 'system_message' in call_item.kwargs:
                system_message_call_args = call_item.kwargs['system_message']
                break

        self.assertIsNotNone(system_message_call_args, "System message was not applied via partial.")
        self.assertIn("IMPORTANT: Sentiment Analysis Data", system_message_call_args)
        self.assertIn("You may be provided with structured sentiment data", system_message_call_args)
        self.assertIn("you MUST incorporate it into your report", system_message_call_args)


    def test_node_output_structure(self):
        """
        Test that the node's output dictionary has the correct structure.
        """
        initial_state = {
            "trade_date": "2024-01-01",
            "company_of_interest": "TestCo",
            "messages": [HumanMessage(content="Analyze TestCo")]
        }

        # Mock SentimentAnalyzer to prevent actual calls if not already done by test specific patch
        with patch('TradingAgents.tradingagents.agents.analysts.social_media_analyst.SentimentAnalyzer') as MockedSA:
            MockedSA.return_value.predict_sentiment.return_value = []
            output = self.social_media_analyst_func(initial_state)

        self.assertIn("messages", output)
        self.assertIn("sentiment_report", output)

        self.assertEqual(output["sentiment_report"], self.mock_llm_invoked_response.content)

        # Output messages should include the original messages, any added sentiment message, and the LLM response
        self.assertTrue(len(output["messages"]) >= 1)
        self.assertIsInstance(output["messages"][-1], AIMessage) # Last message should be AIMessage from LLM
        self.assertEqual(output["messages"][-1].content, "Mocked LLM sentiment report.")


if __name__ == '__main__':
    unittest.main()
