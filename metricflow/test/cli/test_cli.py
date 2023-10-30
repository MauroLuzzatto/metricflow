from __future__ import annotations

import logging
import shutil
import textwrap
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import pytest
from _pytest.fixtures import FixtureRequest
from dbt_semantic_interfaces.parsing.dir_to_model import (
    parse_yaml_files_to_validation_ready_semantic_manifest,
)
from dbt_semantic_interfaces.parsing.objects import YamlConfigFile
from dbt_semantic_interfaces.test_utils import base_semantic_manifest_file

from metricflow.cli.main import (
    dimension_values,
    dimensions,
    entities,
    health_checks,
    metrics,
    query,
    tutorial,
    validate_configs,
)
from metricflow.protocols.sql_client import SqlClient, SqlEngine
from metricflow.test.fixtures.cli_fixtures import MetricFlowCliRunner
from metricflow.test.fixtures.setup_fixtures import MetricFlowTestSessionState
from metricflow.test.model.example_project_configuration import EXAMPLE_PROJECT_CONFIGURATION_YAML_CONFIG_FILE
from metricflow.test.snapshot_utils import assert_object_snapshot_equal

logger = logging.getLogger(__name__)


# TODO: Use snapshots to compare CLI output for all tests here.


def test_query(capsys: pytest.CaptureFixture, cli_runner: MetricFlowCliRunner) -> None:  # noqa: D
    # Disabling capsys to resolve error "ValueError: I/O operation on closed file". Better solution TBD.
    with capsys.disabled():
        resp = cli_runner.run(query, args=["--metrics", "bookings", "--group-by", "metric_time"])
    # case insensitive matches are needed for snowflake due to the capitalization thing
    engine_is_snowflake = cli_runner.cli_context.sql_client.sql_engine_type is SqlEngine.SNOWFLAKE
    assert "bookings" in resp.output or ("bookings" in resp.output.lower() and engine_is_snowflake)
    assert resp.exit_code == 0


def test_list_dimensions(capsys: pytest.CaptureFixture, cli_runner: MetricFlowCliRunner) -> None:  # noqa: D
    # Disabling capsys to resolve error "ValueError: I/O operation on closed file". Better solution TBD.
    with capsys.disabled():
        resp = cli_runner.run(dimensions, args=["--metrics", "bookings"])

    assert "ds" in resp.output
    assert resp.exit_code == 0


def test_list_metrics(capsys: pytest.CaptureFixture, cli_runner: MetricFlowCliRunner) -> None:  # noqa: D
    # Disabling capsys to resolve error "ValueError: I/O operation on closed file". Better solution TBD.
    with capsys.disabled():
        resp = cli_runner.run(metrics)

    assert "bookings_per_listing: listing__capacity_latest" in resp.output
    assert resp.exit_code == 0


def test_get_dimension_values(capsys: pytest.CaptureFixture, cli_runner: MetricFlowCliRunner) -> None:  # noqa: D
    # Disabling capsys to resolve error "ValueError: I/O operation on closed file". Better solution TBD.
    with capsys.disabled():
        resp = cli_runner.run(dimension_values, args=["--metrics", "bookings", "--dimension", "booking__is_instant"])

    actual_output_lines = sorted(resp.output.split("\n"))
    assert ["", "• False", "• True"] == actual_output_lines
    assert resp.exit_code == 0


@contextmanager
def create_directory(directory_path: str) -> Iterator[None]:
    """Creates a temporary directory (errors if it exists) and removes it."""
    path = Path(directory_path)
    path.mkdir(parents=True, exist_ok=True)
    yield
    shutil.rmtree(path)


def test_validate_configs(capsys: pytest.CaptureFixture, cli_runner: MetricFlowCliRunner) -> None:  # noqa: D
    yaml_contents = textwrap.dedent(
        """\
        semantic_model:
          name: bad_semantic_model
          node_relation:
            schema_name: some_schema
            alias: some_table
          defaults:
            agg_time_dimension: ds
          dimensions:
            - name: country
              type: categorical
        """
    )
    bad_semantic_model = YamlConfigFile(filepath="inline_for_test", contents=yaml_contents)
    # JSON-stored manifests from dbt are not transformed, so we run this test on that style of output
    manifest = parse_yaml_files_to_validation_ready_semantic_manifest(
        [EXAMPLE_PROJECT_CONFIGURATION_YAML_CONFIG_FILE, base_semantic_manifest_file(), bad_semantic_model],
        apply_transformations=False,
    ).semantic_manifest

    target_directory = Path().absolute() / "target"
    with create_directory(target_directory.as_posix()):
        manifest_file = target_directory / "semantic_manifest.json"
        manifest_file.write_text(manifest.json())

        # Disabling capsys to resolve error "ValueError: I/O operation on closed file". Better solution TBD.
        with capsys.disabled():
            resp = cli_runner.run(validate_configs)

        assert "ERROR" in resp.output
        assert resp.exit_code == 0


def test_health_checks(capsys: pytest.CaptureFixture, cli_runner: MetricFlowCliRunner) -> None:  # noqa: D
    # Disabling capsys to resolve error "ValueError: I/O operation on closed file". Better solution TBD.
    with capsys.disabled():
        resp = cli_runner.run(health_checks)

    assert "SELECT 1: Success!" in resp.output
    assert resp.exit_code == 0


def test_tutorial_message(capsys: pytest.CaptureFixture, cli_runner: MetricFlowCliRunner) -> None:
    """Tests the message output of the tutorial.

    The tutorial now essentially compiles a semantic manifest and then asks the user to run dbt seed,
    so from an end user perspective it's little more than the output with -m.

    The tutorial currently requires execution from a dbt project path. Rather than go all the way on testing the
    tutorial given the path and dbt project requirements, we simply check the message output. When we allow for
    project path overrides it might warrant a more complete test of the semantic manifest building steps in the
    tutorial flow.
    """
    # Disabling capsys to resolve error "ValueError: I/O operation on closed file". Better solution TBD.
    with capsys.disabled():
        resp = cli_runner.run(tutorial, args=["-m"])
    assert "Please run the following steps" in resp.output
    assert "dbt seed" in resp.output


def test_list_entities(capsys: pytest.CaptureFixture, cli_runner: MetricFlowCliRunner) -> None:  # noqa: D
    # Disabling capsys to resolve error "ValueError: I/O operation on closed file". Better solution TBD.
    with capsys.disabled():
        resp = cli_runner.run(entities, args=["--metrics", "bookings"])

    assert "guest" in resp.output
    assert "host" in resp.output


@pytest.mark.sql_engine_snapshot
def test_saved_query(  # noqa: D
    request: FixtureRequest,
    capsys: pytest.CaptureFixture,
    mf_test_session_state: MetricFlowTestSessionState,
    cli_runner: MetricFlowCliRunner,
    sql_client: SqlClient,
) -> None:
    # Disabling capsys to resolve error "ValueError: I/O operation on closed file". Better solution TBD.
    with capsys.disabled():
        resp = cli_runner.run(
            query, args=["--saved-query", "p0_booking", "--order", "metric_time__day,listing__capacity_latest"]
        )

    assert resp.exit_code == 0

    assert_object_snapshot_equal(
        request=request,
        mf_test_session_state=mf_test_session_state,
        obj_id="cli_output",
        obj=resp.output,
        sql_client=sql_client,
    )


@pytest.mark.sql_engine_snapshot
def test_saved_query_with_where(  # noqa: D
    request: FixtureRequest,
    capsys: pytest.CaptureFixture,
    mf_test_session_state: MetricFlowTestSessionState,
    cli_runner: MetricFlowCliRunner,
    sql_client: SqlClient,
) -> None:
    # Disabling capsys to resolve error "ValueError: I/O operation on closed file". Better solution TBD.
    with capsys.disabled():
        resp = cli_runner.run(
            query,
            args=[
                "--saved-query",
                "p0_booking",
                "--order",
                "metric_time__day,listing__capacity_latest",
                "--where",
                "{{ Dimension('listing__capacity_latest') }} > 4",
            ],
        )

    assert resp.exit_code == 0

    assert_object_snapshot_equal(
        request=request,
        mf_test_session_state=mf_test_session_state,
        obj_id="cli_output",
        obj=resp.output,
        sql_client=sql_client,
    )


@pytest.mark.sql_engine_snapshot
def test_saved_query_with_limit(  # noqa: D
    request: FixtureRequest,
    capsys: pytest.CaptureFixture,
    mf_test_session_state: MetricFlowTestSessionState,
    cli_runner: MetricFlowCliRunner,
    sql_client: SqlClient,
) -> None:
    # Disabling capsys to resolve error "ValueError: I/O operation on closed file". Better solution TBD.
    with capsys.disabled():
        resp = cli_runner.run(
            query,
            args=[
                "--saved-query",
                "p0_booking",
                "--order",
                "metric_time__day,listing__capacity_latest",
                "--limit",
                "3",
            ],
        )

    assert resp.exit_code == 0

    assert_object_snapshot_equal(
        request=request,
        mf_test_session_state=mf_test_session_state,
        obj_id="cli_output",
        obj=resp.output,
        sql_client=sql_client,
    )


def test_saved_query_explain(  # noqa: D
    capsys: pytest.CaptureFixture,
    mf_test_session_state: MetricFlowTestSessionState,
    cli_runner: MetricFlowCliRunner,
) -> None:
    # Disabling capsys to resolve error "ValueError: I/O operation on closed file". Better solution TBD.
    with capsys.disabled():
        resp = cli_runner.run(
            query,
            args=["--explain", "--saved-query", "p0_booking", "--order", "metric_time__day,listing__capacity_latest"],
        )

    # Currently difficult to compare explain output due to randomly generated IDs.
    assert resp.exit_code == 0
