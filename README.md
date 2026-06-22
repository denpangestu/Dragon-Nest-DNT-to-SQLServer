# DragonNest DNT to SQL Importer

A Python utility to parse and migrate DragonNest `.dnt` data files into a SQL Server database. This tool streamlines the process of editing game data by moving it from binary format to a queryable SQL environment.

## Features
- **Automatic Database Setup**: Creates the database if it doesn't exist.
- **Dynamic Schema Generation**: Automatically creates tables based on DNT file structure.
- **Bulk Insert**: High-performance data insertion using `fast_executemany`.
- **Metadata Support**: Keeps track of file structure for potential reverse conversion.

## Prerequisites
- Python 3.x
- [pyodbc](https://github.com/mkleehammer/pyodbc)
- [tqdm](https://github.com/tqdm/tqdm)
- ODBC Driver 17/18 for SQL Server

## Setup
1. Configure your database settings in the `DB_CONFIG` dictionary.
2. Ensure the DNT files are located in the path specified in `DNT_FOLDER`.
3. Run the script: `python bulk_dnt_import.py`
