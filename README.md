# HYGAS-AI Digital Twin

Digital twin for a municipal-solid-waste (MSW) gasification plant that
produces hydrogen via water-gas-shift conversion, PSA purification, and
CHP utilisation. NACHIP pilot project (DOK-ING d.o.o., Zagreb, Croatia).

See [CLAUDE.md](CLAUDE.md) for the project context, what is modelled and what is Assumed or Missing, and the open
questions. The repository holds the Streamlit app (11 tabs, `app.py`), the Python plant model (`python/`), a scheduled
runtime driver (`scripts/run_continuous_cycle.py`, `.github/workflows/continuous_cycle.yml`) and the test suite (`tests/`).

## Live Dashboard

**URL:** https://hygas-ai-digital-twin-dvernddvdppzagjdytbxnx.streamlit.app/

Deploy by pointing Streamlit Community Cloud at this repo with `app.py`
as the entry point; it installs `requirements.txt` automatically.
