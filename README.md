# Private study launcher

A minimal Streamlit launcher. This repository contains no study dataset, participant records, access password, API keys, or Google credentials.

The application source is loaded server-side from a restricted Google Drive file using the existing `drive.file` authorization. A required SHA-256 digest pins the reviewed source. The study itself checks its access password before displaying content. Configure all secrets in the Streamlit hosting dashboard.

Deploy `app.py` with Python 3.12. Set `KDRAMA_SOURCE_FILE_ID`, `KDRAMA_SOURCE_SHA256` and the study's server-side configuration in Secrets. The source and results folders remain restricted; publishing this generic launcher does not make them public.
