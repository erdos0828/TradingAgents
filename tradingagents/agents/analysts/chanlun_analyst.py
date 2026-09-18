from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.utils.agent_utils import (
    get_chanlun_analysis,
    get_instrument_context_from_state,
    get_language_instruction,
)


def create_chanlun_analyst(llm):

    def chanlun_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = get_instrument_context_from_state(state)

        tools = [
            get_chanlun_analysis,
        ]

        system_message = (
            """You are a technical analyst specializing in Chan Theory (Chanlun, 缠论). Your role is to interpret the Chan-theory market structure — bi (strokes), xd (segments), pivots (zhongshu), buy/sell points and divergences — for the ticker under analysis.

Call the get_chanlun_analysis tool with the ticker and the current date to retrieve the Chanlun structure computed from daily bars. If the tool reports that chanlun-core is unavailable or the data is insufficient, state that plainly in the report and do not invent any Chanlun structure.

When the data is available, write a detailed report covering:
1. **Current structure position**: which bi/xd is active, whether it is done, and where the latest close sits relative to the most recent pivot (ZG/ZD zone).
2. **Buy/sell points**: any 1st/2nd/3rd buy or sell points on the latest bi/xd, what they imply, and whether they are already invalidated by price.
3. **Divergences**: bi/segment/consolidation/trend divergences on the recent lines and what they suggest about momentum exhaustion.
4. **Scenario outlook**: 2-3 scenarios for the likely next structure move (e.g. pivot breakout, pullback into the zone, trend continuation), each with the key price levels that confirm or invalidate it.

Cross-reference the Chanlun levels (pivot ZG/ZD/GG/DD, buy/sell point prices) explicitly as concrete price levels. Be specific and actionable; where the structure is ambiguous, say so rather than forcing a conclusion."""
            + """ Make sure to append a Markdown table at the end of the report summarizing the key Chanlun levels (pivot zone, active bi/xd endpoints, buy/sell points) and their trading implications."""
            + get_language_instruction()
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
                    " You have access to the following tools: {tool_names}."
                    " Today's date is {current_date}; treat it as 'now' for all analysis and tool-call date ranges. {instrument_context}\n"
                    "{system_message}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        chain = prompt | llm.bind_tools(tools)

        result = chain.invoke(state["messages"])

        report = ""

        if len(result.tool_calls) == 0:
            report = result.content

        return {
            "messages": [result],
            "chanlun_report": report,
        }

    return chanlun_analyst_node
