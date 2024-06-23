# openstack-service-api

오픈스택을 이용하여 주요 자원(vm, volume, floating ip)들을 관리할 수 있는 백엔드 서비스 프로젝트

[google slide](https://docs.google.com/presentation/d/1swDHVlhkv99rBADjdWaGL1U5HjXt3Ee3RHNWTwPqklM/edit?usp=sharing)

[api specification](https://github.com/choieastsea/openstack-service-api/blob/main/openapi_spec.json)

## how to

1. docker-compose
  `docker-compose up -d`
2. uvicorn
  `uvicorn backend.main:app`

## 개발 환경 및 주요 라이브러리

- python 3.11
- poetry 
- fastapi
- openstack devstack (keystone, nova, neutron, cinder API)
- aiohttp
- mysql

## service architecture

```
.
├── README.md
├── backend
│   ├── api
│   │	└─ routing과 response을 담당하는 계층
│   ├── app.py
│   │	└─ fastapi app을 생성
│   ├── client
│   │	└─ AsyncClient 기반으로 openstack api를 호출하기 위한 컴포넌트
│   ├── core
│   │	└─ config, session을 관리
│   ├── log_conf.yaml
│   │	└─ 로그 설정 파일
│   ├── main.py
│   │	└─  서비스 엔트리 파일
│   ├── model
│   │	└─  DB model(table)을 관리
│   ├── repository
│   │	└─  repository layer
│   ├── schema
│   │	└─  DTO
│   ├── service
│   │	└─  service layer (business logic 처리)
│   └── util
├── test
│   ├── api
│   │	└─ E2E test
│   ├── conftest.py
│   │	└─ test를 위한 fixture
│   ├── mock
│   │	└─ 외부 api mocking
│   ├── pytest.ini
│   │	└─ 테스트 설정 파일
│   └── unit
│    	└─ unit test
├── Dockerfile
│	└─ 서버 컨테이너를 위한 도커파일
├── docker-compose.yml
│	└─ 서버 + mysql 통합 배포를 위한 컴포즈 파일
├── openapi_spec.json
│	└─ api 문서
├── poetry.lock
└── pyproject.toml : 의존성 패키지
```

## db schema

### Server

| field | type | description | comment |
|-------|------|-------------|---------|
| server_id | UUID | 서버id | NN |
| name | varchar(255) | 이름 | NN, 삭제되지 않은 것 중 unique |
| description | varchar(255) | 설명 |  |
| fk_project_id | UUID | 프로젝트id | NN |
| fk_flavor_id | UUID | 사양id | NN |
| fk_network_id | UUID | 네트워크id |  |
| fk_port_id | UUID | 포트id |  |
| fixed_address | char(15) | 고정ip주소 |  |
| created_at | datetime | 생성시간 | NN |
| updated_at | datetime | 수정시간 | NN |
| deleted_at | datetime | 삭제시간 | soft delete |

### Floatingip

| field | type | description | comment |
|-------|------|-------------|---------|
| floatingip_id | UUID | 유동ip id | NN |
| ip_address | char(15) | 유동ip 주소 | NN |
| description | varchar(255) | 설명 |  |
| fk_project_id | UUID | 프로젝트id | NN |
| fk_network_id | UUID | 네트워크id |  |
| fk_port_id | UUID | 연결된 포트id | 서버와 연결된 경우에 값 존재 |
| created_at | datetime | 생성시간 | NN |
| updated_at | datetime | 수정시간 | NN |
| deleted_at | datetime | 삭제시간 | soft delete |

### Volume

| field | type | description | comment |
|-------|------|-------------|---------|
| volume_id | UUID | 볼륨 id | NN |
| name | varchar(255) | 이름 | NN, 삭제되지 않은 것 중 unique |
| description | varchar(255) | 설명 |  |
| volume_type | varchar(12) | 볼륨 타입 | HDD |
| fk_project_id | UUID | 프로젝트id | NN |
| fk_server_id | UUID | 연결된 서버id | 서버 연결 없이 존재 가능 |
| fk_image_id | UUID | 이미지id | 이미지(os) 없다면 빈 볼륨, 이미지가 있다면 루트 볼륨으로 간주 |
| created_at | datetime | 생성시간 | NN |
| updated_at | datetime | 수정시간 | NN |
| deleted_at | datetime | 삭제시간 | soft delete |
