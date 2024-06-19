import enum
from datetime import datetime
from uuid import UUID
from sqlalchemy import Column, Uuid, String, Enum, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from backend.core.db import Base


class RuleDirection(str, enum.Enum):
    INGRESS = 'ingress'
    EGRESS = 'egress'


class RuleProtocol(enum.Enum):
    # protocol 출처 : https://docs.openstack.org/api-ref/network/v2/index.html#list-security-group-rules
    ANY = 0
    AH = 51
    DCCP = 33
    EGP = 8
    ESP = 50
    GRE = 47
    ICMP = 1
    ICMPV6 = 58
    IGMP = 2
    IPIP = 4
    IPV6_ENCAP = 41
    IPV6_FRAG = 44
    IPV6_ICMP = 58
    IPV6_NONXT = 59
    IPV6_OPTS = 60
    IPV6_ROUTE = 43
    OSPF = 89
    PGM = 113
    RSVP = 46
    SCTP = 132
    TCP = 6
    UDP = 17
    UDPLITE = 136
    VRRP = 112


class Rule(Base):
    __tablename__ = 'rule'
    rule_id: UUID = Column(Uuid(as_uuid=True), primary_key=True, comment='rule id')
    description: str = Column(String(255))
    ethertype: str = Column(String(4), default='IPv4', nullable=False)
    direction: RuleDirection = Column(Enum(RuleDirection), nullable=False, comment='방향')
    protocol: RuleProtocol = Column(Enum(RuleProtocol), comment='프로토콜')
    port_range_min: int = Column(Integer)
    port_range_max: int = Column(Integer)
    cidr: str = Column(String(18))
    fk_security_group_id: UUID = Column(Uuid(as_uuid=True), ForeignKey('securitygroup.securitygroup_id'),
                                        comment='연관된 보안그룹 id')
    created_at: datetime = Column(DateTime, comment='생성시간')
    updated_at: datetime = Column(DateTime, comment='수정시간')
    deleted_at: datetime = Column(DateTime, nullable=True, comment='삭제시간')


class SecurityGroup(Base):
    __tablename__ = 'securitygroup'
    securitygroup_id: UUID = Column(Uuid(as_uuid=True), primary_key=True, comment='security group id')
    name: str = Column(String(255), nullable=False, comment='security group name')
    description: str = Column(String(255))
    fk_project_id: UUID = Column(Uuid(as_uuid=True))
    created_at: datetime = Column(DateTime, comment='생성시간')
    updated_at: datetime = Column(DateTime, comment='수정시간')
    deleted_at: datetime = Column(DateTime, nullable=True, comment='삭제시간')

    rules = relationship('Rule', backref='securitygroup')  # related rules


class Server_SecurityGroup(Base):
    __tablename__ = 'server_securitygroup'
    fk_server_id: UUID = Column(Uuid(as_uuid=True), ForeignKey('server.server_id'), primary_key=True)
    fk_securitygroup_id: UUID = Column(Uuid(as_uuid=True), ForeignKey('securitygroup.securitygroup_id'),
                                       primary_key=True)
