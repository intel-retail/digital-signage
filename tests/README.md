## Functional Test Steps

1. Install test dependencies:

	```sh
	cd ./tests/functional/
	python3 -m venv env
	source env/bin/activate
	pip3 install -r ../requirements.txt
	```

2. Prepare a disposable deployment before running the full suite:

   > [!NOTE]
   > Docker and Docker Compose must be installed. Configure `.env`, build images
   > with `make build` from the repository root. The test fixture checks required
	> PID/AIG model files and runs `make download_models` if they are missing (it
	> skips the optional LTX-Video export). It supplies temporary valid WebRTC
	> credentials through `ENV_FILE` and does not change `.env`.

3. Run all functional tests:

	```sh
	pytest -v -s --html=report.html
	```

	The deployment fixture is function-scoped: each live test validates
	configuration, runs `make up`, and runs `make down` during teardown.
	Controlled-detection tests temporarily pause PID and replace the web UI catalog;
	`make down` removes the test stack and its temporary configuration afterward.
	The repeated-deployment test waits for containers to be running, then checks
	MQTT and HTTP readiness on each cycle instead of waiting for every health timer.
	The web UI's Docker healthcheck is a no-op that runs every five minutes, so the
	tests check its actual HTTP and MQTT readiness instead of waiting on that status.

	> [!WARNING]
	> Each live test runs `make up` and `make down`; `make up` first runs
	> `make down`. These commands remove Docker volumes, including Qdrant data. Run
	> the suite only on a disposable deployment, not on a shared or valuable stack.

	The default URL is `https://127.0.0.1:5000`. For another host or port, set
	`DS_TEST_BASE_URL`. Include the host in `NO_PROXY` when using a proxy. Tests
	accept self-signed certificates by default; set `REQUESTS_CA_BUNDLE` to a
	trusted CA bundle to enable verification.

	Install Nmap on the host for the published TCP-port scan; the test skips if it
	is missing. The scan covers only stack-published TCP ports, not all host ports
	or UDP reachability.

4. Configuration tests can also run by themselves without Docker or a deployed
   application (GNU Make is required):

	```sh
	pytest -v -s --html=configuration_report.html test_configuration.py
	```

	They check host IP and WebRTC credentials using temporary files, without
	changing the application's `.env`.

5. To run only selected groups, use pytest markers. These commands still start
   and clean up the stack when the selected tests require it:

	```sh
	pytest -v -s -m security test_security.py
	pytest -v -s -m stability test_stability.py
	pytest -v -s -m advertisements test_advertisements.py
	pytest -v -s -m destructive
	```

6. GPU and NPU functional tests:

	```sh
	pytest -v -s test_GPU_docker.py
	pytest -v -s test_NPU_docker.py
	```

	Each group checks DL Streamer PID inference using the real simulation video,
	then checks AIG image generation by requesting an image on that device. The
	PID test uses a temporary Compose override and restores the default pipeline
	configuration afterward. A test is skipped when its host device node is absent.
	NPU image generation is experimental and may take several minutes on first use;
	the NPU cache is reused when available. NPU is not supported for AIG video
	generation, so the NPU group tests image ads only. A complete run still uses
		 the deployment fixture and `make down` after each test module; run it only on a disposable
	deployment.

	Security checks include Compose settings, runtime container settings, published
	ports, recent logs, HTTP headers, and malformed ad requests. Digital Signage
	has no InfluxDB/Grafana login equivalent; its MQTT broker is private and allows
	anonymous clients inside the Compose network.