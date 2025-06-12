from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import ToolMessage, HumanMessage
import time
import json
from TradingAgents.tradingagents.predictive_models.sentiment_analyzer import SentimentAnalyzer # Adjust path if necessary

def create_social_media_analyst(llm, toolkit):
    # Initialize SentimentAnalyzer instance
    sentiment_analyzer_instance = SentimentAnalyzer(model_type='vader')

    def social_media_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        # company_name = state["company_of_interest"] # ticker is used for company name

        if toolkit.config["online_tools"]:
            tools = [toolkit.get_stock_news_openai]
            # Tool name for checking ToolMessage, assuming it matches the function name
            data_tool_name = "get_stock_news_openai"
        else:
            tools = [toolkit.get_reddit_stock_info]
            data_tool_name = "get_reddit_stock_info"

        # --- Sentiment Analysis Integration ---
        messages_for_llm = list(state["messages"]) # Make a mutable copy
        texts_for_sentiment_analysis = []
        raw_tool_outputs = []

        for message in reversed(messages_for_llm): # Check recent messages first
            if isinstance(message, ToolMessage) and message.name == data_tool_name:
                try:
                    # Assuming tool output is a JSON string representing a list of posts/news
                    # Or a string that can be directly analyzed.
                    content_data = message.content
                    raw_tool_outputs.append(content_data) # Store raw output for context if needed

                    if isinstance(content_data, str):
                        try:
                            # Try parsing if it's a JSON string list of objects
                            parsed_data = json.loads(content_data)
                            if isinstance(parsed_data, list):
                                for item in parsed_data:
                                    if isinstance(item, dict):
                                        # Look for 'title' or 'content' or 'selftext' keys
                                        if "title" in item and item["title"]:
                                            texts_for_sentiment_analysis.append(str(item["title"]))
                                        if "content" in item and item["content"]:
                                            texts_for_sentiment_analysis.append(str(item["content"]))
                                        elif "selftext" in item and item["selftext"]: # For Reddit posts
                                            texts_for_sentiment_analysis.append(str(item["selftext"]))
                            else: # If not a list, maybe a single string item that needs analysis
                                texts_for_sentiment_analysis.append(str(parsed_data))

                        except json.JSONDecodeError:
                            # If not JSON, treat the whole content as a single text
                            texts_for_sentiment_analysis.append(content_data)
                    elif isinstance(content_data, list): # If already a list
                         for item in content_data:
                            if isinstance(item, dict):
                                if "title" in item and item["title"]:
                                    texts_for_sentiment_analysis.append(str(item["title"]))
                                if "content" in item and item["content"]:
                                    texts_for_sentiment_analysis.append(str(item["content"]))
                                elif "selftext" in item and item["selftext"]:
                                    texts_for_sentiment_analysis.append(str(item["selftext"]))
                            elif isinstance(item, str):
                                texts_for_sentiment_analysis.append(item)
                    # Break if we found the most recent relevant tool message
                    if texts_for_sentiment_analysis:
                        break
                except Exception as e:
                    print(f"Error processing ToolMessage content for sentiment analysis: {e}")
                    # Potentially add this error as context for the LLM.
                    # messages_for_llm.append(HumanMessage(content=f"Note: Error processing tool output for sentiment: {e}"))


        structured_sentiment_data_summary = "No specific text data found from tools for sentiment analysis in the current message history."
        if texts_for_sentiment_analysis:
            # Deduplicate texts before sending to analyzer to save processing
            unique_texts = sorted(list(set(texts_for_sentiment_analysis)))
            if unique_texts:
                print(f"Found {len(unique_texts)} unique texts for sentiment analysis.")
                sentiment_results = sentiment_analyzer_instance.predict_sentiment(unique_texts)

                # Prepare a summary or the full data for the LLM
                # For now, let's create a string summary.
                formatted_sentiments = []
                for res in sentiment_results:
                    formatted_sentiments.append(
                        f"- Text: \"{res['text'][:100]}...\" -> Label: {res['sentiment_label']}, Score: {res['sentiment_score']:.2f}"
                    )
                if formatted_sentiments:
                    structured_sentiment_data_summary = "Sentiment Analysis Results:\n" + "\n".join(formatted_sentiments)
                else:
                    structured_sentiment_data_summary = "Sentiment analysis was run but yielded no results."

                # Add this structured sentiment data as a new HumanMessage for the LLM to consider.
                # This message should be placed strategically, perhaps after the tool output it refers to,
                # or more simply, appended to the message list for the LLM.
                # For simplicity, appending it. The LLM should be instructed via system prompt on how to find/use it.
                messages_for_llm.append(HumanMessage(content=structured_sentiment_data_summary))
            else:
                structured_sentiment_data_summary = "No textual data extracted for sentiment analysis."
                messages_for_llm.append(HumanMessage(content=structured_sentiment_data_summary))

        # --- End Sentiment Analysis Integration ---

        # Updated System Message
        system_message = (
            "You are a social media and company specific news researcher/analyst. Your task is to analyze social media posts, recent company news, and public sentiment for a specific company over the past week. "
            "You will be given the company's name. Your objective is to write a comprehensive long report detailing your analysis, insights, and implications for traders and investors. "
            "Consider all available information: social media discussions, sentiment data (if provided), and recent company news. "
            "\n\n**IMPORTANT: Sentiment Analysis Data**\n"
            "You may be provided with structured sentiment data from an automated analysis of texts (e.g., Reddit posts, news headlines). This data typically includes the original text snippet, a sentiment label (positive, negative, neutral), and a sentiment score (e.g., VADER compound score). "
            "When this data is available (it will be presented as a 'Sentiment Analysis Results:' section in a recent message), you MUST incorporate it into your report. Specifically:\n"
            "- Summarize the overall sentiment trends indicated by this data.\n"
            "- Mention the proportion or general sense of positive, negative, and neutral posts/items.\n"
            "- Highlight any specific items with particularly strong sentiment scores (either positive or negative) that support your broader analysis or offer unique insights.\n"
            "- Use this sentiment data to add depth and quantitative backing to your qualitative observations from social media and news.\n"
            "If no specific sentiment data is provided, state that and rely on your general interpretation of the texts.\n\n"
            "Do not simply state that trends are mixed; provide detailed and fine-grained analysis and insights that may help traders make decisions. "
            "Make sure to append a Markdown table at the end of the report to organize key points, making it easy to read."
        )


        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK; another assistant with different tools"
                    " will help where you left off. Execute what you can to make progress."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    " You have access to the following tools: {tool_names}.\n{system_message}"
                    "For your reference, the current date is {current_date}. The current company we want to analyze is {ticker}",
                ),
                MessagesPlaceholder(variable_name="messages"), # This will now include our new HumanMessage with sentiment
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(ticker=ticker)

        chain = prompt | llm.bind_tools(tools)

        # Invoke the chain with the potentially modified messages list
        result = chain.invoke({"messages": messages_for_llm})

        # The sentiment report from the LLM should now ideally reflect the analyzed sentiment.
        # The 'messages' in the output state should include the LLM's response.
        # We also want to ensure our added HumanMessage (with sentiment) is part of the history for future turns if any.
        final_messages_for_state = messages_for_llm + [result]


        return {
            "messages": final_messages_for_state, # Pass the full history including the new sentiment message and LLM response
            "sentiment_report": result.content,
        }

    return social_media_analyst_node
