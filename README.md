<p align="center">
    <img src="https://img.shields.io/github/last-commit/jo-chr/ddra?color=blue">
</p>

# Data-Driven Reliability Assessment of Cyber-Physical Production Systems

This is a tool for data-driven reliability assessment of Cyber-physical Production Systems (CPPS).

## Getting Started

:information_source: *Tested with Python 3.11*

[PySPN](https://github.com/jo-chr/pyspn.git) is a requirement for this tool. Clone it and place it in the root folder of the tool like so:
```
.
├── components/
├── output/
├── pyspn/
├── raw_data/
├── cs_two_station.ini
├── cs_two_station.ipynb
└── ...
```

### via git

```bash
git clone https://github.com/jo-chr/ddra.git  # 1. Clone repository
pip install -r requirements.txt  # 2. Install requirements
git clone https://github.com/jo-chr/pyspn.git  # 3. Clone PySPN repo, install its requirments, and place it in this folder
python3 cs_two_station.py  # 4. Run example
```

## Interactive Example

An interactive example of how to use the tool can be found in `cs_two_station.ipynb`

## Usage & Attribution

contact jofr@mmmi.sdu.dk


 
