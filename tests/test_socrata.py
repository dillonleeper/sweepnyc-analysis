from unittest.mock import Mock, patch

import pytest
import requests

from sweepnyc.socrata import fetch_rows


@patch("sweepnyc.socrata.time.sleep")
@patch("sweepnyc.socrata.requests.get")
def test_fetch_rows_retries_on_timeout_then_succeeds(mock_get, mock_sleep):
    ok_response = Mock(status_code=200)
    ok_response.json.return_value = [{"a": 1}]
    mock_get.side_effect = [
        requests.exceptions.ReadTimeout("read timed out"),
        ok_response,
    ]

    rows = fetch_rows("abcd-1234")

    assert rows == [{"a": 1}]
    assert mock_get.call_count == 2
    mock_sleep.assert_called_once()


@patch("sweepnyc.socrata.time.sleep")
@patch("sweepnyc.socrata.requests.get")
def test_fetch_rows_raises_after_exhausting_retries(mock_get, mock_sleep):
    mock_get.side_effect = requests.exceptions.ReadTimeout("read timed out")

    with pytest.raises(requests.exceptions.ReadTimeout):
        fetch_rows("abcd-1234")

    assert mock_get.call_count == 3


@patch("sweepnyc.socrata.time.sleep")
@patch("sweepnyc.socrata.requests.get")
def test_fetch_rows_does_not_retry_client_errors(mock_get, mock_sleep):
    bad_response = Mock(status_code=404)
    bad_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
        "404 not found", response=bad_response
    )
    mock_get.return_value = bad_response

    with pytest.raises(requests.exceptions.HTTPError):
        fetch_rows("abcd-1234")

    assert mock_get.call_count == 1
    mock_sleep.assert_not_called()
