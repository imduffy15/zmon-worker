import requests
import pytest

from mock import MagicMock

from zmon_worker_monitor.builtins.plugins.kairosdb import KairosdbWrapper, DATAPOINTS_ENDPOINT, HttpError

URL = 'http://kairosdb'


@pytest.fixture(params=[
    (
        {'name': 'check1-metric'},
        {'queries': [{'results': [1, 2]}]},
    ),
    (
        {'name': 'check1-metric', 'tags': {'application_id': ['my-app']}},
        {'queries': [{'results': [1, 2, 3]}]},
    ),
    (
        {'name': 'check1-metric', 'aggregators': [{'name': 'sum'}]},
        {'queries': [{'results': [1, 2, 3, 4]}]},
    ),
    (
        {'name': 'check1-metric', 'aggregators': [{'name': 'sum'}], 'start': 1, 'time_unit': 'hours'},
        {'queries': [{'results': [1, 2, 3, 4, 5, 6, 7, 8]}]},
    ),
    (
        {'name': 'check1-metric'},
        requests.Timeout(),
    ),
    (
        {'name': 'check1-metric'},
        requests.ConnectionError(),
    )
])
def fx_query(request):
    return request.param


def resp_mock(res, failure=False):
    resp = MagicMock()
    resp.ok = True if not failure else False
    resp.json.return_value = res

    return resp


def requests_mock(resp, failure=None):
    req = MagicMock()

    if failure is not None:
        req.side_effect = failure
    else:
        req.return_value = resp

    return req


def get_final_url():
    return URL + '/' + DATAPOINTS_ENDPOINT


def get_query(kwargs):
    start = kwargs.get('start', -5)
    time_unit = kwargs.get('time_unit', 'seconds')

    q = {
        'start_relative': {
            'value': start,
            'unit': time_unit
        },
        'metrics': [{
            'name': kwargs['name'],
        }]
    }

    if 'aggregators' in kwargs:
        q['metrics'][0]['aggregators'] = kwargs.get('aggregators')

    if 'tags' in kwargs:
        q['metrics'][0]['tags'] = kwargs.get('tags')

    return q


def test_kairosdb_query(monkeypatch, fx_query):
    kwargs, res = fx_query

    failure = True if isinstance(res, Exception) else False

    if failure:
        resp = resp_mock(res, failure=True)
        post = requests_mock(resp, failure=res)
    else:
        resp = resp_mock(res)
        post = requests_mock(resp)

    monkeypatch.setattr('requests.Session.post', post)

    cli = KairosdbWrapper(URL)

    q = get_query(kwargs)

    if failure:
        with pytest.raises(HttpError):
            cli.query(**kwargs)
    else:
        result = cli.query(**kwargs)
        assert result == res['queries'][0]

    post.assert_called_with(get_final_url(), json=q)


def test_kairosdb_oauth2(monkeypatch):
    token = 123
    get = MagicMock()
    get.return_value = token
    monkeypatch.setattr('tokens.get', get)

    cli = KairosdbWrapper(URL, oauth2=True)

    assert 'Bearer {}'.format(token) == cli._KairosdbWrapper__session.headers['Authorization']