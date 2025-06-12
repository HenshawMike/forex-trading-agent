# sentiment_analyzer.py
# This file will contain the SentimentAnalyzer class for predicting sentiment from text data.

import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer

# --- Download VADER lexicon if not already present ---
try:
    nltk.data.find('sentiment/vader_lexicon.zip')
except nltk.downloader.DownloadError:
    print("Downloading VADER lexicon from NLTK...")
    nltk.download('vader_lexicon')
# --- End VADER lexicon download ---


# Expected input data format:
# The primary input for sentiment analysis will be a list of text strings.
# These strings can originate from various sources, such as:
# - News headlines
# - Article snippets
# - Reddit post titles
# - Reddit post content (selftext)
# Example: ["Stock A is soaring!", "Company B reports unexpected losses.", "New product C looks promising."]

# Preprocessing steps for VADER (VADER handles many of these internally):
# 1. Text Cleaning:
#    - VADER is designed to handle raw text, including emojis, punctuation, and capitalization.
#    - Minimal cleaning might sometimes be beneficial but often not strictly necessary.
# 2. Tokenization:
#    - VADER has its own tokenizer.
# 3. Handling Text Length:
#    - VADER processes text as is; no strict length limits like some transformer models.

class SentimentAnalyzer:
    """
    A class to analyze sentiment from text data using VADER (Valence Aware Dictionary and sEntiment Reasoner).
    """

    def __init__(self, model_type: str = "vader"):
        """
        Initializes the SentimentAnalyzer.

        Currently supports 'vader'. In the future, could support other model types.

        Args:
            model_type (str, optional): Type of the sentiment analysis model to use.
                                        Defaults to "vader".
        """
        self.model_type = model_type
        self.analyzer = None

        if self.model_type.lower() == "vader":
            # Initialize VADER Sentiment Intensity Analyzer
            self.analyzer = SentimentIntensityAnalyzer()
            print("SentimentAnalyzer initialized with VADER.")
        # Elif other model types like "transformers" could be added here
        # elif self.model_type.lower() == "transformers":
        #     # Placeholder for Hugging Face model loading
        #     # self.tokenizer = AutoTokenizer.from_pretrained(model_name_or_path)
        #     # self.model = AutoModelForSequenceClassification.from_pretrained(model_name_or_path)
        #     print(f"SentimentAnalyzer initialized with Transformers model: {model_name_or_path}")
        else:
            raise ValueError(f"Unsupported model_type: {self.model_type}. Supported types: 'vader'.")


    def predict_sentiment(self, text_data: list[str]) -> list[dict]:
        """
        Predicts sentiment for a list of text strings using the initialized model.

        Args:
            text_data (list[str]): A list of text strings to analyze.
                                   Example: ["Great news today!", "Market is down."]

        Returns:
            list[dict]: A list of dictionaries, where each dictionary contains:
                        - 'text': The original input text.
                        - 'sentiment_label': The predicted sentiment label ('positive', 'negative', 'neutral').
                        - 'sentiment_score': The VADER compound score (ranges from -1 to 1).
        """
        if not isinstance(text_data, list) or not all(isinstance(text, str) for text in text_data):
            raise ValueError("Input text_data must be a list of strings.")

        if not self.analyzer and self.model_type.lower() == "vader":
            # This case should ideally not be hit if __init__ is always called correctly.
            print("VADER analyzer not initialized. Re-initializing.")
            self.analyzer = SentimentIntensityAnalyzer()

        predictions = []

        if self.model_type.lower() == "vader":
            if not self.analyzer:
                 raise RuntimeError("VADER SentimentIntensityAnalyzer not initialized properly.")
            for text in text_data:
                # Get VADER polarity scores
                # Example: {'neg': 0.0, 'neu': 0.323, 'pos': 0.677, 'compound': 0.6369}
                vs = self.analyzer.polarity_scores(text)

                compound_score = vs['compound']

                # Determine sentiment label based on compound score
                if compound_score >= 0.05:
                    sentiment_label = "positive"
                elif compound_score <= -0.05:
                    sentiment_label = "negative"
                else:
                    sentiment_label = "neutral"

                predictions.append({
                    "text": text,
                    "sentiment_label": sentiment_label,
                    "sentiment_score": compound_score  # Using compound score as the primary sentiment score
                })
        # Add logic for other model types here if expanded in the future
        # elif self.model_type.lower() == "transformers":
            # ...
            # pass

        return predictions

if __name__ == '__main__':
    # Example Usage (for testing when this file is run directly)
    print("--- Initializing VADER Sentiment Analyzer for __main__ test ---")
    analyzer = SentimentAnalyzer(model_type="vader") # Explicitly specify vader

    sample_texts = [
        "This is great news for the company! Its stock is soaring.",
        "The market experienced a slight downturn today, which is bad.",
        "Overall, the outlook is poor and quite negative.",
        "Analysts are optimistic about the new product.",
        "Customer feedback has been very good and positive.",
        "VADER is smart, handsome, and funny.", # Example from VADER's own documentation
        "VADER is smart, handsome, and funny!", # With exclamation
        "VADER is not smart, handsome, nor funny.", # Negation
        "The food was good, but the service was terrible.", # Mixed sentiment
        "This is an okay movie.",
        "What a terrible day."
    ]

    print("\n--- Predicting sentiment for sample texts ---")
    sentiments = analyzer.predict_sentiment(sample_texts)

    for item in sentiments:
        print(f"Text: \"{item['text']}\" -> Label: {item['sentiment_label']} (Compound Score: {item['sentiment_score']:.4f})")

    print("\n--- Testing with empty list ---")
    sentiments_empty = analyzer.predict_sentiment([])
    print(f"Result for empty list: {sentiments_empty}")

    print("\n--- Testing with invalid input ---")
    try:
        analyzer.predict_sentiment("not a list")
    except ValueError as e:
        print(f"Caught expected error: {e}")

    # Test initialization with unsupported model type
    print("\n--- Testing with unsupported model type ---")
    try:
        failed_analyzer = SentimentAnalyzer(model_type="unsupported_dummy_type")
    except ValueError as e:
        print(f"Caught expected error for unsupported type: {e}")
