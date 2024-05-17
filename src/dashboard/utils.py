"""utils.py - Utility functions for the Streamlit app."""

import sys
import logging

# Set up logging.
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create a console handler and set the level to INFO.
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
logger.addHandler(console_handler)


def is_streamlit_running() -> bool:
    """Check if Streamlit is running.

    Returns:
        bool: True if Streamlit is running, False otherwise.
    """
    try:
        import streamlit as st
        # Check if Streamlit is running by accessing a Streamlit attribute
        if hasattr(st, 'runtime') and st.runtime.exists():
            return True
        else:
            return False
    except ImportError:
        return False


def main():
    """Run utils as a Streamlit app e.g.
    python -m streamlit run src/dashboard/utils.py"""
    # Create a Streamlit app.
    import streamlit as st
    st.title("Streamlit App")

    # Check if Streamlit is running.
    if is_streamlit_running():
        logger.info("Streamlit is running.")
        st.write("Streamlit is running.")
    else:
        logger.info("Streamlit is not running.")
        st.write("Streamlit is not running.")


if __name__ == "__main__":
    main()
