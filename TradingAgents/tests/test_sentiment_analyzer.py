import unittest
import sys
import os

# Adjust the Python path to include the parent directory of 'TradingAgents'
# This allows finding the TradingAgents module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from TradingAgents.tradingagents.predictive_models.sentiment_analyzer import SentimentAnalyzer

class TestSentimentAnalyzerVader(unittest.TestCase):
    """
    Test cases for the SentimentAnalyzer class using the VADER model.
    """

    @classmethod
    def setUpClass(cls):
        """
        Set up the SentimentAnalyzer instance once for all tests in this class.
        This also implicitly tests the VADER lexicon download/check in SentimentAnalyzer's module.
        """
        try:
            cls.analyzer = SentimentAnalyzer(model_type='vader')
        except Exception as e:
            # If NLTK download fails in a restricted environment, this provides a clearer message.
            if "nltk.download" in str(e) or "SSL" in str(e).upper():
                print("\nNLTK VADER lexicon download might have failed. "
                      "Please ensure 'vader_lexicon' is downloaded by running: "
                      "python -m nltk.downloader vader_lexicon\n"
                      "Skipping SentimentAnalyzer tests if lexicon is unavailable.")
                # We can't raise SkipTest directly in setUpClass easily across Python versions
                # without more complex solutions. Instead, we'll check for self.analyzer in tests.
                cls.analyzer = None
            else:
                raise e


    def setUp(self):
        """
        Check if the analyzer was initialized. If not (due to setUpClass failure), skip test.
        """
        if not hasattr(TestSentimentAnalyzerVader, 'analyzer') or TestSentimentAnalyzerVader.analyzer is None:
            self.skipTest("SentimentAnalyzer could not be initialized (likely VADER lexicon issue).")
        self.analyzer = TestSentimentAnalyzerVader.analyzer


    def test_initialization(self):
        """Test model initialization with valid and invalid types."""
        self.assertIsNotNone(self.analyzer.analyzer, "VADER analyzer should be initialized.")
        self.assertEqual(self.analyzer.model_type, "vader")

        with self.assertRaises(ValueError):
            SentimentAnalyzer(model_type="unsupported_type")

    def test_predict_sentiment_positive(self):
        """Test with known positive sentences."""
        texts = [
            "This is a great and wonderful day!",
            "I love this product, it's amazing.",
            "The team did an excellent job, fantastic results.",
            "Absolutely brilliant and superb performance."
        ]
        results = self.analyzer.predict_sentiment(texts)
        self.assertEqual(len(results), len(texts))
        for i, res in enumerate(results):
            self.assertEqual(res["text"], texts[i])
            self.assertEqual(res["sentiment_label"], "positive", f"Text: '{texts[i]}' not positive.")
            self.assertGreaterEqual(res["sentiment_score"], 0.05, f"Text: '{texts[i]}' score not >= 0.05.")

    def test_predict_sentiment_negative(self):
        """Test with known negative sentences."""
        texts = [
            "This is a terrible and awful experience.",
            "I hate this situation, it's dreadful.",
            "The results were poor and very disappointing.",
            "This is the worst thing ever."
        ]
        results = self.analyzer.predict_sentiment(texts)
        self.assertEqual(len(results), len(texts))
        for i, res in enumerate(results):
            self.assertEqual(res["text"], texts[i])
            self.assertEqual(res["sentiment_label"], "negative", f"Text: '{texts[i]}' not negative.")
            self.assertLessEqual(res["sentiment_score"], -0.05, f"Text: '{texts[i]}' score not <= -0.05.")

    def test_predict_sentiment_neutral(self):
        """Test with known neutral sentences."""
        texts = [
            "The sky is blue today.",
            "This is a pen.",
            "The report will be delivered tomorrow.",
            "My favorite color is blue." # VADER might find 'favorite' slightly positive.
        ]
        results = self.analyzer.predict_sentiment(texts)
        self.assertEqual(len(results), len(texts))

        # VADER's threshold for neutral is compound score > -0.05 and < 0.05
        # For "My favorite color is blue.", VADER gives compound: 0.4588, label: positive.
        # This shows that true "neutrality" can be subjective for VADER.
        # We will check the specific labels VADER assigns based on its compound score logic.

        expected_labels = ["neutral", "neutral", "neutral", "positive"] # Adjusted for VADER's behavior
        for i, res in enumerate(results):
            self.assertEqual(res["text"], texts[i])
            self.assertEqual(res["sentiment_label"], expected_labels[i],
                             f"Text: '{texts[i]}' expected '{expected_labels[i]}' but got '{res['sentiment_label']}' with score {res['sentiment_score']}.")
            if expected_labels[i] == "neutral":
                 self.assertTrue(-0.05 < res["sentiment_score"] < 0.05,
                                 f"Text: '{texts[i]}' score {res['sentiment_score']} not in neutral range (-0.05, 0.05).")


    def test_predict_sentiment_mixed(self):
        """Test with a list of mixed sentiment sentences."""
        texts = [
            "This is great!", # positive
            "This is bad.",   # negative
            "This is a cat."  # neutral
        ]
        results = self.analyzer.predict_sentiment(texts)
        self.assertEqual(len(results), len(texts))

        self.assertEqual(results[0]["sentiment_label"], "positive")
        self.assertGreaterEqual(results[0]["sentiment_score"], 0.05)

        self.assertEqual(results[1]["sentiment_label"], "negative")
        self.assertLessEqual(results[1]["sentiment_score"], -0.05)

        self.assertEqual(results[2]["sentiment_label"], "neutral")
        self.assertTrue(-0.05 < results[2]["sentiment_score"] < 0.05)


    def test_predict_sentiment_empty_list(self):
        """Test with an empty list as input."""
        results = self.analyzer.predict_sentiment([])
        self.assertEqual(results, [])

    def test_predict_sentiment_list_with_empty_string(self):
        """Test with a list containing an empty string or whitespace."""
        texts = ["", "   "]
        results = self.analyzer.predict_sentiment(texts)
        self.assertEqual(len(results), len(texts))
        for i, res in enumerate(results):
            self.assertEqual(res["text"], texts[i])
            # VADER typically scores empty or whitespace strings as neutral (compound score 0.0)
            self.assertEqual(res["sentiment_label"], "neutral", f"Text: '{texts[i]}' not neutral.")
            self.assertEqual(res["sentiment_score"], 0.0, f"Text: '{texts[i]}' score not 0.0.")

    def test_predict_sentiment_special_characters_and_emojis(self):
        """Test with sentences containing special characters and emojis."""
        # VADER is designed to handle emojis and some special characters well.
        texts = [
            "This is so good 😊👍", # Positive emoji
            "I am very sad 😞",    # Negative emoji
            "What on earth is this?!", # Exclamations, question marks
            "This product is *amazing*." # Markdown-like emphasis
        ]
        results = self.analyzer.predict_sentiment(texts)
        self.assertEqual(len(results), len(texts))

        # Expected VADER behavior:
        # "This is so good 😊👍" -> positive
        # "I am very sad 😞" -> negative
        # "What on earth is this?!" -> VADER might see this as slightly negative or neutral depending on interpretation of "What on earth"
        # "This product is *amazing*." -> positive

        self.assertEqual(results[0]["sentiment_label"], "positive")
        self.assertGreaterEqual(results[0]["sentiment_score"], 0.05)

        self.assertEqual(results[1]["sentiment_label"], "negative")
        self.assertLessEqual(results[1]["sentiment_score"], -0.05)

        # For "What on earth is this?!", VADER's output score is -0.3182 -> negative
        self.assertEqual(results[2]["sentiment_label"], "negative", f"Score: {results[2]['sentiment_score']}")
        self.assertLessEqual(results[2]["sentiment_score"], -0.05)

        self.assertEqual(results[3]["sentiment_label"], "positive")
        self.assertGreaterEqual(results[3]["sentiment_score"], 0.05)

    def test_input_validation(self):
        """Test that predict_sentiment raises ValueError for invalid input types."""
        with self.assertRaisesRegex(ValueError, "Input text_data must be a list of strings."):
            self.analyzer.predict_sentiment("not a list")

        with self.assertRaisesRegex(ValueError, "Input text_data must be a list of strings."):
            self.analyzer.predict_sentiment([123, "a string"])


if __name__ == '__main__':
    unittest.main()
