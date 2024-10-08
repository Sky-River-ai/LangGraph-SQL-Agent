import streamlit as st
from langchain.schema import StrOutputParser
from langchain.schema.runnable import RunnablePassthrough
from langchain_community.utilities import SQLDatabase
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, Sequence
from langchain_community.llms import Ollama
import pymysql

# Initialize Ollama
llm = Ollama(model="llama3.2:3b-instruct-fp16")  # or whichever model you're using with Ollama

# MySQL connection details
mysql_config = {
    "host":"localhost",
    "port":3306,
    "database":"customer_behavior",
    "username":"root",
    "password":"abc**",
    "table":"customer", # Default MySQL port, change if yours is different
}

# Initialize your MySQL database
db = SQLDatabase.from_uri(f"mysql+pymysql://{mysql_config['username']}:{mysql_config['password']}@{mysql_config['host']}:{mysql_config['port']}/{mysql_config['database']}")

# Define the state
class State(TypedDict):
    query: str
    sql: str
    result: str
    thought: str

# Define the nodes
def generate_sql(state: State) -> State:
    prompt = f"""Given the following user query, generate a MySQL query to answer it:

Query: {state['query']}

The available tables in the database are: {db.get_table_names()}

MySQL Query:"""
    sql = llm.invoke(prompt)
    return {"sql": sql, "thought": "Generated MySQL query based on user input."}

def execute_sql(state: State) -> State:
    result = db.run(state["sql"])
    return {"result": result, "thought": "Executed MySQL query and obtained result."}

def interpret_result(state: State) -> State:
    prompt = f"""Given the following MySQL query and its result, provide a natural language interpretation:

Query: {state['sql']}

Result: {state['result']}

Interpretation:"""
    interpretation = llm.predict(prompt)
    return {"result": interpretation, "thought": "Interpreted MySQL result in natural language."}

# Define the edges
def should_continue(state: State) -> Annotated[Sequence[str], "next_node"]:
    if "result" not in state:
        return ["execute_sql"]
    elif isinstance(state["result"], str) and state["result"].strip().startswith("SELECT"):
        return ["execute_sql"]
    else:
        return ["interpret_result"]

# Create the graph
workflow = StateGraph(State)

# Add the nodes
workflow.add_node("generate_sql", generate_sql)
workflow.add_node("execute_sql", execute_sql)
workflow.add_node("interpret_result", interpret_result)

# Add the edges
workflow.set_entry_point("generate_sql")
workflow.add_conditional_edges("generate_sql", should_continue)
workflow.add_conditional_edges("execute_sql", should_continue)
workflow.add_edge("interpret_result", END)

# Compile the graph
app = workflow.compile()

# Streamlit UI
st.title("MySQL Query Assistant (Ollama)")

# User input
user_query = st.text_input("Enter your question about the MySQL database:")

if user_query:
    # Process the query through your LangGraph
    result = app.invoke({"query": user_query})
    
    # Display the results
    st.subheader("Generated MySQL Query:")
    st.code(result["sql"], language="sql")
    
    st.subheader("Query Result:")
    st.write(result["result"])
    
    st.subheader("Interpretation:")
    st.write(result["thought"])

# Add a section to display available tables
st.sidebar.subheader("Available Tables")
for table in db.get_usable_table_names():
    st.sidebar.write(table)
