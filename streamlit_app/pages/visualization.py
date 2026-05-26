import streamlit as st


def run():
    st.title("Workflow Visualization")
    st.markdown("Lightweight workflow node visualization")
    dot = """
    digraph G {
      rankdir=LR;
      node [shape=box];
      ingest -> embed -> retrieve -> rank -> respond;
    }
    """
    st.graphviz_chart(dot)
    st.write("Node timing and order will be shown here during execution (placeholder).")

if __name__ == '__main__':
    run()
