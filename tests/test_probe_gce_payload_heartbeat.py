from scripts.probe_gce_payload_heartbeat import parse_last_json_object


def test_parse_last_json_object_ignores_remote_shell_noise() -> None:
    output = "(anon):setopt:7: can't change option: monitor\n{\"kind\": \"payload\", \"generation\": 3}\n"

    assert parse_last_json_object(output) == {"kind": "payload", "generation": 3}
