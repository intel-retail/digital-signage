# Changelog

All notable changes to this project are documented in this file.

## [2026.1] - June 2026

### Added
- Added a `.github` directory with CODEOWNERS, contributing guide, and PR template files. ([998f874])
- Added drivers for PTL. ([a8fd2b7])
- Added multi-object detection support. ([d1a5902])
- Added WCL integration. ([a745d65])
- Reorganized the repository and enabled NGINX. ([475f58b])
- Added pull request and scan workflows. ([402fc06])

### Changed
- Updated `.github/CONTRIBUTING.md`. ([2221c13])
- Updated `.github/CONTRIBUTING.md`. ([e4816df])
- Updated DL Streamer Pipeline Server to `2026.0-rc1` tag. ([a439412])

### Removed
- Removed basket video. ([8eaca2c])

### Fixed
- Fixed a ChromaDB issue. ([ac8e48e])
- Fixed the Pillow version in `requirements.txt`. ([c59acd9])

### Security
- Bumped `pillow` from `12.1.0` to `12.1.1` in `aig/src`. ([60379d3])
- Bumped `flask` from `3.0.0` to `3.1.3` in `web-ui`. ([75143e5])
- Bumped `flask` from `3.1.2` to `3.1.3` in `aig/src`. ([5d29dae])
- Bumped `requests` from `2.32.5` to `2.33.0` in `web-ui`. ([0f73556])
- Bumped `pillow` from `12.1.1` to `12.2.0` in `aig/src`. ([715d09b])
- Bumped `pillow` from `12.1.1` to `12.2.0` in `web-ui`. ([e501953])
- Bumped `diffusers` from `0.33.1` to `0.38.0` in `aig/src`. ([be09a7e])
- Bumped `diffusers` from `0.33.1` to `0.38.0` in `aig`. ([5d10d77])
- Bumped `urllib3` from `2.6.3` to `2.7.0` in `aig/src`. ([eb4ab1c])
- Upgraded `urllib3` to the latest version in AIG. ([4779eaf])

---
[ac8e48e]: https://github.com/intel-retail/digital-signage/commit/ac8e48e32c0792d46f965bf61cd37a0eea8277f6
[60379d3]: https://github.com/intel-retail/digital-signage/commit/60379d301a6755e5f90748c609ded46ecb5ba3c2
[75143e5]: https://github.com/intel-retail/digital-signage/commit/75143e5d6e7298001a99b75448c8518c6e5413e7
[998f874]: https://github.com/intel-retail/digital-signage/commit/998f874a2ad2fd2857d72aa53a22cc156648ad0e
[c59acd9]: https://github.com/intel-retail/digital-signage/commit/c59acd9f1fba0202785b77618e4913d4ff324292
[2221c13]: https://github.com/intel-retail/digital-signage/commit/2221c130fc85977dadd83f0ef4cf3264074487db
[e4816df]: https://github.com/intel-retail/digital-signage/commit/e4816df363bb793776dcb47b0e63467add27d4fc
[5d29dae]: https://github.com/intel-retail/digital-signage/commit/5d29dae79c0f739d7781f50891e43d946a383303
[a8fd2b7]: https://github.com/intel-retail/digital-signage/commit/a8fd2b731facad516823f1d2b9f90f79d0b6a378
[8eaca2c]: https://github.com/intel-retail/digital-signage/commit/8eaca2c8cc8d091b977039b3375c3ee9e15b5fa7
[a439412]: https://github.com/intel-retail/digital-signage/commit/a439412be8a72d2d7d9869fe5ec336f6617f83c9
[0f73556]: https://github.com/intel-retail/digital-signage/commit/0f735566bdeae7e2dc9b405f452c70af95ac3b9b
[715d09b]: https://github.com/intel-retail/digital-signage/commit/715d09bcaf54075e5335940e2f4e6234960f9875
[d1a5902]: https://github.com/intel-retail/digital-signage/commit/d1a59024a967e5dbc7c0b238e90ec2b7de25f702
[e501953]: https://github.com/intel-retail/digital-signage/commit/e5019537477bffe1442a4d5a0b9cebf645b7c9b2
[be09a7e]: https://github.com/intel-retail/digital-signage/commit/be09a7e5cf171c50e27afc5a2543d92272699103
[5d10d77]: https://github.com/intel-retail/digital-signage/commit/5d10d775f4f44b6f0d2ec8967912f6a0f3f40264
[eb4ab1c]: https://github.com/intel-retail/digital-signage/commit/eb4ab1c94969e10b2cd376ae82cff5a381d3e422
[4779eaf]: https://github.com/intel-retail/digital-signage/commit/4779eaf1433cdba1c2734728de01acf1f660c632
[a745d65]: https://github.com/intel-retail/digital-signage/commit/a745d65379a2dedfe6735a2dd131a2317bc58e6f
[475f58b]: https://github.com/intel-retail/digital-signage/commit/475f58bac60b7fb0699fe62204347393e7578dae
[402fc06]: https://github.com/intel-retail/digital-signage/commit/402fc060aa22c773aaae0be310dbb4fe29b4cf0e

---

## [1.0.0] - January 2026

### Added
- Added an option in PID scripts to remove components. ([f73a429])
- Added item video support in PID Docker Compose for the end-to-end demo. ([3968c0f])
- Added products, transactions, APIs, and MQTT pool support in PCA. ([c968ec7])
- Added the initial AIG implementation. ([fc253a1])
- Added the initial ASE implementation extending AIG. ([1e234f8])
- Added a step to enable RTSP camera at source. ([#26])
- Added AIG improvements to reduce memory consumption. ([#31])

### Changed
- Added the initial project structure. ([88b685b])
- Added the initial project push updates. ([df62472])
- Updated PID initial definition. ([e969259])
- Updated PID Docker Compose configuration. ([e3cb132])
- Updated PID certificate directory setup. ([2870e3a])
- Updated initial PID scripts. ([bc97fa8])
- Updated installPID dependency checks. ([906392e])
- Created the runPID script. ([3162794])
- Updated PID runScript with NPU user setup. ([891c230])
- Added the initial PCA Docker file and server setup. ([d44ba48])
- Updated PCA management scripts and transaction database integration. ([443fad9])
- Updated PCA MQTT topics with an initial approach. ([17a8615])
- Updated PCA weekly and weekly-hh24 product probability processing and API. ([3b722e4])
- Updated PCA association rules and APIs. ([13a92b8])
- Updated ASE API and sample data. ([0729a0c])
- Added BOR server and scripts for milestone 1. ([002eb38])
- Added a comprehensive digital signage system for context-aware cross-selling. ([c912c24])
- Updated architecture diagrams. ([#33])
- Updated RTSP pipeline for Axis camera. ([#34])
- Updated public ports and `export-requirements.txt`. ([#35])
- Merged main branch updates. ([0a3209e])
- Updated overview text. ([dcaff95])
- Addressed review comments. ([2c7e033])

### Removed
- Added confirmation before removing PID components. ([c0fa62e])

### Fixed
- Fixed a minor issue in runPID. ([64d0d54])
- Fixed a minor AIG issue in documentation-related updates. ([f7eeb67])
- Fixed a minor ASE issue in `testASE.py`. ([a0e70d8])
- Fixed font alignment of pre-defined ads in web UI. ([#25])
- Fixed database-related issues and third-party file updates. ([#30])
- Fixed the non-root user issue in Docker Compose. ([#36])
- Fixed support for devices without GPU or NPU. ([642d12e])
- Fixed alignment issues in `README.md`. ([6d76d37])
- Fixed minor documentation issues in `README.md`. ([a6b8947])

### Security
- Fixed Trivy and Bandit scan findings in digital signage. ([#24])
- Fixed Trivy scan findings in the AIG server. ([#28])
- Fixed Trivy Dockerfile configuration scan findings. ([#32])

### Documentation
- Updated `README.md` with PID scripts and outputs. ([e860e76])
- Updated PCA documentation. ([b0ec8d7])
- Updated AIG documentation and scripts. ([4a096ab])
- Updated ASE documentation. ([1514d4c])
- Updated BOR documentation. ([7cc9daa])
- Completed digital signage cleanup and documentation. ([#29])
- Updated `README.md`. ([eb36ee7])
- Updated `README.md`. ([69337a4])

---
[#24]: https://github.com/intel-retail/digital-signage/pull/24
[#25]: https://github.com/intel-retail/digital-signage/pull/25
[#26]: https://github.com/intel-retail/digital-signage/pull/26
[#28]: https://github.com/intel-retail/digital-signage/pull/28
[#29]: https://github.com/intel-retail/digital-signage/pull/29
[#30]: https://github.com/intel-retail/digital-signage/pull/30
[#31]: https://github.com/intel-retail/digital-signage/pull/31
[#32]: https://github.com/intel-retail/digital-signage/pull/32
[#33]: https://github.com/intel-retail/digital-signage/pull/33
[#34]: https://github.com/intel-retail/digital-signage/pull/34
[#35]: https://github.com/intel-retail/digital-signage/pull/35
[#36]: https://github.com/intel-retail/digital-signage/pull/36
[88b685b]: https://github.com/intel-retail/digital-signage/commit/88b685b6e251119d4c6b9231bf7a90d8632935f7
[df62472]: https://github.com/intel-retail/digital-signage/commit/df6247246979eca5deec8ecf46c3f73437f10257
[e969259]: https://github.com/intel-retail/digital-signage/commit/e969259afc3439bfaa5a2deb1fcedaa36e233e78
[e3cb132]: https://github.com/intel-retail/digital-signage/commit/e3cb1325a455fdd8a61a14067ab67c59036ed812
[2870e3a]: https://github.com/intel-retail/digital-signage/commit/2870e3a5538c512185cfc128d49932820ad62ac5
[bc97fa8]: https://github.com/intel-retail/digital-signage/commit/bc97fa8d7da478a3463337bb072dc7e789e8a2b4
[906392e]: https://github.com/intel-retail/digital-signage/commit/906392eb6b5262e0d6be26878b7df7ab4e2d35ee
[3162794]: https://github.com/intel-retail/digital-signage/commit/316279496d72c10f2c95931141464390cef68cf4
[f73a429]: https://github.com/intel-retail/digital-signage/commit/f73a429c119612a33a524c3ae9a244355d53f636
[64d0d54]: https://github.com/intel-retail/digital-signage/commit/64d0d54c9043d998ca843b71a2e2c52a03d766a6
[3968c0f]: https://github.com/intel-retail/digital-signage/commit/3968c0fe138eb477eb68458fd1ab5579122e4947
[e860e76]: https://github.com/intel-retail/digital-signage/commit/e860e766a626a82f047a0b6d7773eacab94634ca
[891c230]: https://github.com/intel-retail/digital-signage/commit/891c230ce7d0038096568d873ca31e585f72dec1
[c0fa62e]: https://github.com/intel-retail/digital-signage/commit/c0fa62eea5c8e94baf9e380bc4328b5dc19ea35e
[d44ba48]: https://github.com/intel-retail/digital-signage/commit/d44ba4834efebcc6dd9763fb517897bf6fd5f6ab
[443fad9]: https://github.com/intel-retail/digital-signage/commit/443fad90e1f793aa170e0c94723e54eb68fc1934
[17a8615]: https://github.com/intel-retail/digital-signage/commit/17a86152b7120a08e28598ea76713a1ac30c252b
[c968ec7]: https://github.com/intel-retail/digital-signage/commit/c968ec7bebd86c7c724fea5dd5e48bcc848279b2
[3b722e4]: https://github.com/intel-retail/digital-signage/commit/3b722e4d5fb515033df58168428e8510c1f00966
[13a92b8]: https://github.com/intel-retail/digital-signage/commit/13a92b86f61208882cbc675bba226822a5de15c1
[b0ec8d7]: https://github.com/intel-retail/digital-signage/commit/b0ec8d78ef7ad5c4daf33ec4d46e1d3cdff902e5
[fc253a1]: https://github.com/intel-retail/digital-signage/commit/fc253a1614162a7bc49cb5184f42aab446958546
[4a096ab]: https://github.com/intel-retail/digital-signage/commit/4a096ab4c776c90f7366f5b65c29aa0fac7fd741
[f7eeb67]: https://github.com/intel-retail/digital-signage/commit/f7eeb6746cddf1eee4c396dcc87115c47a4b31a9
[1e234f8]: https://github.com/intel-retail/digital-signage/commit/1e234f89c34460962553dc60ea3f73c5a750b43d
[a0e70d8]: https://github.com/intel-retail/digital-signage/commit/a0e70d8067e1733ae403802f801efac9c2861f13
[0729a0c]: https://github.com/intel-retail/digital-signage/commit/0729a0c49e8b3a1b44cb46b4f2c85ba487a53541
[1514d4c]: https://github.com/intel-retail/digital-signage/commit/1514d4ce2fe7776e5e901b3918fdd9eba8fcc991
[002eb38]: https://github.com/intel-retail/digital-signage/commit/002eb38519dc31b1ebcc1a00b727022ae379987f
[7cc9daa]: https://github.com/intel-retail/digital-signage/commit/7cc9daa15a3044eb8873701d024633119033648b
[c912c24]: https://github.com/intel-retail/digital-signage/commit/c912c24a0f6dff355ea8db7eb08922ef1ec3e621
[0a3209e]: https://github.com/intel-retail/digital-signage/commit/0a3209ee9efd2f77b9a7f00abb4f9f7f08571229
[642d12e]: https://github.com/intel-retail/digital-signage/commit/642d12eace094db9dd8e0d180f31f3ae5c0daee4
[6d76d37]: https://github.com/intel-retail/digital-signage/commit/6d76d371dd6cfa0c8a819f0268f6e62695f4d759
[eb36ee7]: https://github.com/intel-retail/digital-signage/commit/eb36ee7d4fbdfb94bc6add41f54fe8eaf493b152
[dcaff95]: https://github.com/intel-retail/digital-signage/commit/dcaff95b11f1f7c4bb994149e3480f9767eab219
[a6b8947]: https://github.com/intel-retail/digital-signage/commit/a6b89472f433b174d747408566cb404ce8cbc9b0
[2c7e033]: https://github.com/intel-retail/digital-signage/commit/2c7e0337cb72907bbcf1bf3e002f503dea9572d8
[69337a4]: https://github.com/intel-retail/digital-signage/commit/69337a47397132cfb402e5ed41a93b282a7be5ea