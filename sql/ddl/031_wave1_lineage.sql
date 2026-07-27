/*
Purpose:
  Register the validated Wave 1 data-lineage path from the pinned UCI source
  through raw/core objects and seven features to the independent validation
  artifact. This script creates no economic-transmission nodes or edges.
Input tables and evidence:
  audit.source_file, audit.pipeline_run, audit.reconciliation_result,
  audit.test_result, raw.credit_card_client, core.borrower,
  core.account_month, mart.borrower_risk_signal,
  mart.signal_default_summary, mart.risk_band_summary, and
  outputs/qa/validated/latest/wave1_independent_validation.json.
Output definition and grain:
  Versioned `data_lineage` nodes at source file, run, code/object, feature,
  validation-result, and artifact grain, plus two deterministic same-scope edge
  families: retained producer-flow edges and claim-to-source dependency edges.
Observation point:
  The registered analytical definitions observe 2005-09-30. Edge validity
  begins 2026-07-27, the date of independent validation for the supplied run.
Main assumptions:
  Only run W1-20260727-001 and its independently validated source SHA-256 are
  eligible. Definition version 0.1.0 is taken from the validated Gate 3 packet.
  The validation JSON remains the numerical authority; this script copies no
  portfolio value or rate into the graph.
Validation:
  The transaction fails closed on a different run/hash, missing source or run,
  failed SQL/reconciliation evidence, absent run-scoped outputs, missing
  feature columns, conflicting deterministic registration, or an incomplete
  seven-feature path.
*/

\if :{?run_id}
\else
  \echo 'run_id is required: psql -v run_id=W1-20260727-001 ...'
  \quit 2
\endif

\if :{?source_sha256}
\else
  \echo 'source_sha256 is required: psql -v source_sha256=<sha256> ...'
  \quit 2
\endif

BEGIN;

SELECT set_config('credit_risk.lineage_run_id', :'run_id', true);
SELECT set_config(
    'credit_risk.lineage_source_sha256',
    :'source_sha256',
    true
);

DO $precondition$
DECLARE
    v_object_name text;
    v_missing_feature_columns text[];
BEGIN
    IF current_setting('credit_risk.lineage_run_id')
        <> 'W1-20260727-001' THEN
        RAISE EXCEPTION
            'run_id is not the independently validated Wave 1 run';
    END IF;

    IF current_setting('credit_risk.lineage_source_sha256')
        <> '30c6be3abd8dcfd3e6096c828bad8c2f011238620f5369220bd60cfc82700933'
    THEN
        RAISE EXCEPTION
            'source_sha256 does not match the independently validated source';
    END IF;

    IF to_regprocedure(
        'meta.register_node(text,text,text,text,text,text,text)'
    ) IS NULL
       OR to_regprocedure(
           'meta.register_edge(text,bigint,bigint,text,date,text,interval,text,date,text)'
       ) IS NULL THEN
        RAISE EXCEPTION
            'apply sql/ddl/030_meta_graph.sql before Wave 1 lineage';
    END IF;

    FOREACH v_object_name IN ARRAY ARRAY[
        'audit.source_file',
        'audit.pipeline_run',
        'audit.reconciliation_result',
        'audit.test_result',
        'raw.credit_card_client',
        'core.borrower',
        'core.account_month',
        'mart.borrower_risk_signal',
        'mart.signal_default_summary',
        'mart.risk_band_summary'
    ]
    LOOP
        IF to_regclass(v_object_name) IS NULL THEN
            RAISE EXCEPTION
                'required Wave 1 object is absent: %',
                v_object_name;
        END IF;
    END LOOP;

    IF NOT EXISTS (
        SELECT 1
        FROM audit.source_file AS source_file
        WHERE source_file.source_id = 'uci_default_credit_card_clients'
          AND source_file.file_sha256
              = current_setting('credit_risk.lineage_source_sha256')
    ) THEN
        RAISE EXCEPTION
            'validated source identity is absent from audit.source_file';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM audit.pipeline_run AS pipeline_run
        WHERE pipeline_run.pipeline_run_id
              = current_setting('credit_risk.lineage_run_id')
          AND pipeline_run.source_id = 'uci_default_credit_card_clients'
          AND pipeline_run.source_file_sha256
              = current_setting('credit_risk.lineage_source_sha256')
          AND pipeline_run.definition_version = '0.1.0'
          AND pipeline_run.observation_date = DATE '2005-09-30'
          AND pipeline_run.status IN ('succeeded', 'validated')
    ) THEN
        RAISE EXCEPTION
            'run/source/version identity is absent or not execution-complete';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM audit.reconciliation_result AS reconciliation
        WHERE reconciliation.pipeline_run_id
              = current_setting('credit_risk.lineage_run_id')
          AND reconciliation.status = 'fail'
    ) OR EXISTS (
        SELECT 1
        FROM audit.test_result AS test_result
        WHERE test_result.pipeline_run_id
              = current_setting('credit_risk.lineage_run_id')
          AND test_result.status = 'fail'
    ) THEN
        RAISE EXCEPTION
            'failed Wave 1 SQL or reconciliation evidence blocks lineage';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM core.borrower AS borrower
        WHERE borrower.pipeline_run_id
              = current_setting('credit_risk.lineage_run_id')
    ) OR NOT EXISTS (
        SELECT 1
        FROM core.account_month AS account_month
        WHERE account_month.pipeline_run_id
              = current_setting('credit_risk.lineage_run_id')
    ) OR NOT EXISTS (
        SELECT 1
        FROM mart.borrower_risk_signal AS risk_signal
        WHERE risk_signal.pipeline_run_id
              = current_setting('credit_risk.lineage_run_id')
    ) OR NOT EXISTS (
        SELECT 1
        FROM mart.signal_default_summary AS signal_summary
        WHERE signal_summary.pipeline_run_id
              = current_setting('credit_risk.lineage_run_id')
    ) OR NOT EXISTS (
        SELECT 1
        FROM mart.risk_band_summary AS band_summary
        WHERE band_summary.pipeline_run_id
              = current_setting('credit_risk.lineage_run_id')
    ) THEN
        RAISE EXCEPTION
            'one or more required run-scoped Wave 1 outputs are absent';
    END IF;

    SELECT array_agg(required_column.column_name ORDER BY required_column.column_name)
    INTO v_missing_feature_columns
    FROM (
        VALUES
            ('recent_max_delinquency'),
            ('delinquent_months_6m'),
            ('delinquency_deterioration'),
            ('latest_utilization_ratio'),
            ('payment_coverage_ratio'),
            ('zero_payment_streak'),
            ('recent_bill_growth')
    ) AS required_column (column_name)
    WHERE NOT EXISTS (
        SELECT 1
        FROM information_schema.columns AS actual_column
        WHERE actual_column.table_schema = 'mart'
          AND actual_column.table_name = 'borrower_risk_signal'
          AND actual_column.column_name = required_column.column_name
    );

    IF v_missing_feature_columns IS NOT NULL THEN
        RAISE EXCEPTION
            'validated feature columns are absent: %',
            array_to_string(v_missing_feature_columns, ', ');
    END IF;
END;
$precondition$;

DO $register_lineage$
DECLARE
    c_scope constant text := 'data_lineage';
    c_definition_version constant text := '0.1.0';
    c_valid_from constant date := DATE '2026-07-27';
    c_validation_evidence constant text :=
        'outputs/qa/validated/latest/wave1_independent_validation.json';
    v_run_id text := current_setting('credit_risk.lineage_run_id');
    v_source_sha256 text :=
        current_setting('credit_risk.lineage_source_sha256');
    v_source_node_id bigint;
    v_loader_node_id bigint;
    v_raw_table_node_id bigint;
    v_run_node_id bigint;
    v_core_transform_node_id bigint;
    v_borrower_table_node_id bigint;
    v_account_month_table_node_id bigint;
    v_signal_query_node_id bigint;
    v_signal_table_node_id bigint;
    v_summary_query_node_id bigint;
    v_validation_test_node_id bigint;
    v_result_node_id bigint;
    v_artifact_node_id bigint;
    v_feature_node_id bigint;
    v_feature_name text;
    v_feature_count integer := 0;
BEGIN
    v_source_node_id := meta.register_node(
        c_scope,
        'Source',
        'source.uci_default_credit_card_clients',
        v_source_sha256,
        'validated',
        'Hermes',
        'data/raw/default of credit card clients.xls'
    );
    v_loader_node_id := meta.register_node(
        c_scope,
        'Transformation',
        'transformation.uci_default_credit_card_clients.load',
        c_definition_version,
        'validated',
        'Hermes',
        'src/ingestion/load_uci_credit_card.py'
    );
    v_raw_table_node_id := meta.register_node(
        c_scope,
        'Table',
        'raw.credit_card_client',
        c_definition_version,
        'validated',
        'Hermes',
        'raw.credit_card_client'
    );
    v_run_node_id := meta.register_node(
        c_scope,
        'Run',
        'run.' || v_run_id,
        v_run_id,
        'validated',
        'Orchestrator',
        'audit.pipeline_run'
    );
    v_core_transform_node_id := meta.register_node(
        c_scope,
        'Transformation',
        'transformation.wave1.build_core',
        c_definition_version,
        'validated',
        'Data Model',
        'sql/staging/020_build_core.sql'
    );
    v_borrower_table_node_id := meta.register_node(
        c_scope,
        'Table',
        'core.borrower',
        c_definition_version,
        'validated',
        'Data Model',
        'core.borrower'
    );
    v_account_month_table_node_id := meta.register_node(
        c_scope,
        'Table',
        'core.account_month',
        c_definition_version,
        'validated',
        'Data Model',
        'core.account_month'
    );
    v_signal_query_node_id := meta.register_node(
        c_scope,
        'Query',
        'query.wave1.risk_signals',
        c_definition_version,
        'validated',
        'Risk Signal',
        'sql/features/060_risk_signals.sql'
    );
    v_signal_table_node_id := meta.register_node(
        c_scope,
        'Table',
        'mart.borrower_risk_signal',
        c_definition_version,
        'validated',
        'Risk Signal',
        'mart.borrower_risk_signal'
    );
    v_summary_query_node_id := meta.register_node(
        c_scope,
        'Query',
        'query.wave1.signal_summaries',
        c_definition_version,
        'validated',
        'SQL QA',
        'sql/reporting/070_signal_summaries.sql'
    );
    v_validation_test_node_id := meta.register_node(
        c_scope,
        'Test',
        'test.wave1.independent_validation',
        '1.0',
        'validated',
        'Validation',
        'src/validation/wave1_reproduction.py'
    );
    v_result_node_id := meta.register_node(
        c_scope,
        'Result',
        'result.wave1.independent_validation.' || v_run_id,
        v_run_id,
        'validated',
        'Validation',
        c_validation_evidence || '#$.status'
    );
    v_artifact_node_id := meta.register_node(
        c_scope,
        'Artifact',
        'artifact.wave1.independent_validation.' || v_run_id,
        '6a12eee57f22275a759f2493fbad5a3fb68aebfeea29ccd8fc5ba04299f2b4ce',
        'validated',
        'Validation',
        c_validation_evidence
    );

    PERFORM meta.register_edge(
        c_scope,
        v_source_node_id,
        v_loader_node_id,
        'transformed_by',
        c_valid_from,
        NULL,
        NULL,
        'src/ingestion/load_uci_credit_card.py',
        NULL,
        'validated'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_loader_node_id,
        v_raw_table_node_id,
        'supports',
        c_valid_from,
        NULL,
        NULL,
        'sql/ingestion/001_raw_credit_card_client.sql',
        NULL,
        'validated'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_source_node_id,
        v_run_node_id,
        'supports',
        c_valid_from,
        NULL,
        NULL,
        c_validation_evidence,
        NULL,
        'validated'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_raw_table_node_id,
        v_core_transform_node_id,
        'transformed_by',
        c_valid_from,
        NULL,
        NULL,
        'sql/staging/020_build_core.sql',
        NULL,
        'validated'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_run_node_id,
        v_core_transform_node_id,
        'supports',
        c_valid_from,
        NULL,
        NULL,
        c_validation_evidence,
        NULL,
        'validated'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_core_transform_node_id,
        v_borrower_table_node_id,
        'supports',
        c_valid_from,
        NULL,
        NULL,
        'sql/staging/020_build_core.sql',
        NULL,
        'validated'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_core_transform_node_id,
        v_account_month_table_node_id,
        'supports',
        c_valid_from,
        NULL,
        NULL,
        'sql/staging/020_build_core.sql',
        NULL,
        'validated'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_borrower_table_node_id,
        v_signal_query_node_id,
        'transformed_by',
        c_valid_from,
        NULL,
        NULL,
        'sql/features/060_risk_signals.sql',
        NULL,
        'validated'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_account_month_table_node_id,
        v_signal_query_node_id,
        'transformed_by',
        c_valid_from,
        NULL,
        NULL,
        'sql/features/060_risk_signals.sql',
        NULL,
        'validated'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_signal_query_node_id,
        v_signal_table_node_id,
        'supports',
        c_valid_from,
        NULL,
        NULL,
        'sql/features/060_risk_signals.sql',
        NULL,
        'validated'
    );

    FOR v_feature_name IN
        SELECT feature.feature_name
        FROM (
            VALUES
                ('recent_max_delinquency'),
                ('delinquent_months_6m'),
                ('delinquency_deterioration'),
                ('latest_utilization_ratio'),
                ('payment_coverage_ratio'),
                ('zero_payment_streak'),
                ('recent_bill_growth')
        ) AS feature (feature_name)
        ORDER BY feature.feature_name
    LOOP
        v_feature_node_id := meta.register_node(
            c_scope,
            'Feature',
            'mart.borrower_risk_signal.' || v_feature_name,
            c_definition_version,
            'validated',
            'Risk Signal',
            'mart.borrower_risk_signal.' || v_feature_name
        );

        PERFORM meta.register_edge(
            c_scope,
            v_signal_query_node_id,
            v_feature_node_id,
            'supports',
            c_valid_from,
            NULL,
            NULL,
            'sql/features/060_risk_signals.sql',
            NULL,
            'validated'
        );
        PERFORM meta.register_edge(
            c_scope,
            v_signal_table_node_id,
            v_feature_node_id,
            'supports',
            c_valid_from,
            NULL,
            NULL,
            'mart.borrower_risk_signal.' || v_feature_name,
            NULL,
            'validated'
        );
        PERFORM meta.register_edge(
            c_scope,
            v_feature_node_id,
            v_summary_query_node_id,
            'transformed_by',
            c_valid_from,
            NULL,
            NULL,
            'sql/reporting/070_signal_summaries.sql',
            NULL,
            'validated'
        );
        PERFORM meta.register_edge(
            c_scope,
            v_summary_query_node_id,
            v_feature_node_id,
            'computed_from',
            c_valid_from,
            NULL,
            NULL,
            'sql/reporting/070_signal_summaries.sql',
            NULL,
            'validated'
        );
        PERFORM meta.register_edge(
            c_scope,
            v_feature_node_id,
            v_signal_query_node_id,
            'computed_from',
            c_valid_from,
            NULL,
            NULL,
            'sql/features/060_risk_signals.sql',
            NULL,
            'validated'
        );

        v_feature_count := v_feature_count + 1;
    END LOOP;

    PERFORM meta.register_edge(
        c_scope,
        v_summary_query_node_id,
        v_validation_test_node_id,
        'validated_by',
        c_valid_from,
        NULL,
        NULL,
        c_validation_evidence,
        NULL,
        'validated'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_validation_test_node_id,
        v_result_node_id,
        'supports',
        c_valid_from,
        NULL,
        NULL,
        c_validation_evidence,
        NULL,
        'validated'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_run_node_id,
        v_result_node_id,
        'supports',
        c_valid_from,
        NULL,
        NULL,
        c_validation_evidence,
        NULL,
        'validated'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_result_node_id,
        v_artifact_node_id,
        'reported_in',
        c_valid_from,
        NULL,
        NULL,
        c_validation_evidence,
        NULL,
        'validated'
    );

    /*
    Claim-to-source dependency family:
      These edges deliberately point from each downstream object to its
      immediate dependency. They are additive to the historical producer-flow
      edges above and make Artifact -> ... -> Source a bounded forward walk
      over only `computed_from` and `validated_by`.
    */
    PERFORM meta.register_edge(
        c_scope,
        v_artifact_node_id,
        v_result_node_id,
        'computed_from',
        c_valid_from,
        NULL,
        NULL,
        c_validation_evidence,
        NULL,
        'validated'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_result_node_id,
        v_validation_test_node_id,
        'validated_by',
        c_valid_from,
        NULL,
        NULL,
        c_validation_evidence,
        NULL,
        'validated'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_validation_test_node_id,
        v_summary_query_node_id,
        'computed_from',
        c_valid_from,
        NULL,
        NULL,
        c_validation_evidence,
        NULL,
        'validated'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_signal_query_node_id,
        v_borrower_table_node_id,
        'computed_from',
        c_valid_from,
        NULL,
        NULL,
        'sql/features/060_risk_signals.sql',
        NULL,
        'validated'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_signal_query_node_id,
        v_account_month_table_node_id,
        'computed_from',
        c_valid_from,
        NULL,
        NULL,
        'sql/features/060_risk_signals.sql',
        NULL,
        'validated'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_borrower_table_node_id,
        v_core_transform_node_id,
        'computed_from',
        c_valid_from,
        NULL,
        NULL,
        'sql/staging/020_build_core.sql',
        NULL,
        'validated'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_account_month_table_node_id,
        v_core_transform_node_id,
        'computed_from',
        c_valid_from,
        NULL,
        NULL,
        'sql/staging/020_build_core.sql',
        NULL,
        'validated'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_core_transform_node_id,
        v_raw_table_node_id,
        'computed_from',
        c_valid_from,
        NULL,
        NULL,
        'sql/staging/020_build_core.sql',
        NULL,
        'validated'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_raw_table_node_id,
        v_loader_node_id,
        'computed_from',
        c_valid_from,
        NULL,
        NULL,
        'src/ingestion/load_uci_credit_card.py',
        NULL,
        'validated'
    );
    PERFORM meta.register_edge(
        c_scope,
        v_loader_node_id,
        v_source_node_id,
        'computed_from',
        c_valid_from,
        NULL,
        NULL,
        'data/raw/default of credit card clients.xls',
        NULL,
        'validated'
    );

    IF v_feature_count <> 7 THEN
        RAISE EXCEPTION
            'Wave 1 lineage must register exactly seven features';
    END IF;

    IF (
        SELECT count(*)
        FROM meta.node AS feature_node
        WHERE feature_node.graph_scope = c_scope
          AND feature_node.node_type = 'Feature'
          AND feature_node.version = c_definition_version
          AND feature_node.canonical_name IN (
              'mart.borrower_risk_signal.recent_max_delinquency',
              'mart.borrower_risk_signal.delinquent_months_6m',
              'mart.borrower_risk_signal.delinquency_deterioration',
              'mart.borrower_risk_signal.latest_utilization_ratio',
              'mart.borrower_risk_signal.payment_coverage_ratio',
              'mart.borrower_risk_signal.zero_payment_streak',
              'mart.borrower_risk_signal.recent_bill_growth'
          )
    ) <> 7 THEN
        RAISE EXCEPTION
            'registered Wave 1 feature node set is incomplete';
    END IF;
END;
$register_lineage$;

COMMIT;
