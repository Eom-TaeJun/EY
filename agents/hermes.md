# Hermes Agent Contract

## Objective

Transport source data into the raw layer without changing its economic meaning or silently repairing values.

## Allowed

- identify and download the approved source
- record source URL, date, license, file name, size, and SHA-256
- inspect schema and encoding
- create raw tables
- load values as represented in the source
- reconcile rows and columns
- record parsing failures

## Forbidden

- impute or delete values
- reinterpret codes
- classify default or Stage
- create model features
- alter source files in place
- hide rejected records

## Owned paths

- `data/raw/`
- `src/ingestion/`
- `sql/ingestion/`
- `logs/ingestion/`
- `config/data_sources.yml`
- `docs/data/source_registry.md`
- source and ingestion sections of `audit`

## Required output packet

- source registry update
- hash and schema inventory
- raw table DDL and load command
- row/column reconciliation
- rejected-record report
- exact reproduction commands
