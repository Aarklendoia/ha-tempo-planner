# Changelog

## [0.7.2](https://github.com/Aarklendoia/ha-tempo-planner/compare/v0.7.1...v0.7.2) (2026-11-25)


### Bug Fixes

* the entity id no longer overlaps the entity picker ([#38](https://github.com/Aarklendoia/ha-tempo-planner/issues/38)) ([9396d39](https://github.com/Aarklendoia/ha-tempo-planner/commit/9396d39d867c358f94c52e57ecb43ad93c8c9f6c)), closes [#37](https://github.com/Aarklendoia/ha-tempo-planner/issues/37)

## [0.7.1](https://github.com/Aarklendoia/ha-tempo-planner/compare/v0.7.0...v0.7.1) (2026-11-25)


### Bug Fixes

* tell same-named entities apart in the panel ([#35](https://github.com/Aarklendoia/ha-tempo-planner/issues/35)) ([2b0025b](https://github.com/Aarklendoia/ha-tempo-planner/commit/2b0025be884169f86390708ea3ad590a73d35207)), closes [#34](https://github.com/Aarklendoia/ha-tempo-planner/issues/34)

## [0.7.0](https://github.com/Aarklendoia/ha-tempo-planner/compare/v0.6.0...v0.7.0) (2026-11-25)


### Features

* a Tempo Planner panel in the sidebar ([#32](https://github.com/Aarklendoia/ha-tempo-planner/issues/32)) ([521842e](https://github.com/Aarklendoia/ha-tempo-planner/commit/521842eaff07943875aeae861ae474940c69e327)), closes [#27](https://github.com/Aarklendoia/ha-tempo-planner/issues/27)

## [0.6.0](https://github.com/Aarklendoia/ha-tempo-planner/compare/v0.5.1...v0.6.0) (2026-11-25)


### Features

* shed any appliance on red days ([#30](https://github.com/Aarklendoia/ha-tempo-planner/issues/30)) ([288287a](https://github.com/Aarklendoia/ha-tempo-planner/commit/288287a28360d7bb05c53026755133b96fc6ff22))

## [0.5.1](https://github.com/Aarklendoia/ha-tempo-planner/compare/v0.5.0...v0.5.1) (2026-11-25)


### Bug Fixes

* never learn a 0 kWh peak load from the meters ([#24](https://github.com/Aarklendoia/ha-tempo-planner/issues/24)) ([9ad1451](https://github.com/Aarklendoia/ha-tempo-planner/commit/9ad1451dd0a9da24434ad3dcc1c407cfa392931b)), closes [#23](https://github.com/Aarklendoia/ha-tempo-planner/issues/23)

## [0.5.0](https://github.com/Aarklendoia/ha-tempo-planner/compare/v0.4.0...v0.5.0) (2026-11-24)


### Features

* take the car's charging out of the house consumption history ([#21](https://github.com/Aarklendoia/ha-tempo-planner/issues/21)) ([a6dcdce](https://github.com/Aarklendoia/ha-tempo-planner/commit/a6dcdce7a921ac0e53feefa4066afea55c697746)), closes [#20](https://github.com/Aarklendoia/ha-tempo-planner/issues/20)

## [0.4.0](https://github.com/Aarklendoia/ha-tempo-planner/compare/v0.3.0...v0.4.0) (2026-11-24)


### Features

* find tomorrow's solar window to charge the car ([#19](https://github.com/Aarklendoia/ha-tempo-planner/issues/19)) ([db5e2fd](https://github.com/Aarklendoia/ha-tempo-planner/commit/db5e2fd6bb6ad5ee75e1fa2482e6d67297d306d5)), closes [#17](https://github.com/Aarklendoia/ha-tempo-planner/issues/17)
* model and review the car's own charging ([#14](https://github.com/Aarklendoia/ha-tempo-planner/issues/14)) ([2e318ef](https://github.com/Aarklendoia/ha-tempo-planner/commit/2e318ef77f2ff067c2190ff7a48ec6ba5a4891fd)), closes [#13](https://github.com/Aarklendoia/ha-tempo-planner/issues/13)
* recommend the car's charge target by Tempo colour, with trips ([#16](https://github.com/Aarklendoia/ha-tempo-planner/issues/16)) ([21b4684](https://github.com/Aarklendoia/ha-tempo-planner/commit/21b4684a3caff1bf9ec1c25fb10f84f30081249f)), closes [#15](https://github.com/Aarklendoia/ha-tempo-planner/issues/15)
* review each day against what actually happened ([#11](https://github.com/Aarklendoia/ha-tempo-planner/issues/11)) ([3193685](https://github.com/Aarklendoia/ha-tempo-planner/commit/31936855a61ffa9d9e3404665c1ea6dddfe922c9)), closes [#10](https://github.com/Aarklendoia/ha-tempo-planner/issues/10)

## [0.3.0](https://github.com/Aarklendoia/ha-tempo-planner/compare/v0.2.0...v0.3.0) (2026-11-24)


### Features

* charge the home battery only when the Tempo price gap pays ([d934c9e](https://github.com/Aarklendoia/ha-tempo-planner/commit/d934c9e8b0af38a36cb7fb2fbfc4a2f3dfdf9ce0))
* charge the home battery only when the Tempo price gap pays ([b0342d9](https://github.com/Aarklendoia/ha-tempo-planner/commit/b0342d9650749af994bfa4dfe2d8a7f7325b545e))
* learn peak-hour consumption from the recorder ([ccb5215](https://github.com/Aarklendoia/ha-tempo-planner/commit/ccb521589122f75e065d06a82a0a808496d79fee))
* learn peak-hour consumption from the recorder ([d471424](https://github.com/Aarklendoia/ha-tempo-planner/commit/d471424e4b289ae5af39cd7d0cae9d42a1a046dc)), closes [#2](https://github.com/Aarklendoia/ha-tempo-planner/issues/2)
* learn peak-hour consumption per Tempo colour ([#9](https://github.com/Aarklendoia/ha-tempo-planner/issues/9)) ([0a37d28](https://github.com/Aarklendoia/ha-tempo-planner/commit/0a37d2864e9fd376ce510ac7552dc44c0d03c355)), closes [#8](https://github.com/Aarklendoia/ha-tempo-planner/issues/8)

## [0.2.0](https://github.com/Aarklendoia/ha-tempo-planner/compare/v0.1.0...v0.2.0) (2026-11-23)


### Features

* house settings at setup, minimum car charge, explained plan ([86184e9](https://github.com/Aarklendoia/ha-tempo-planner/commit/86184e9aa246675096e0eb8deca607e42d8d8ab0))
