from backend.client.cinder import CinderClient
from backend.client.glance import GlanceClient
from backend.client.keystone import KeystoneClient
from backend.client.neutron import NeutronClient
from backend.client.nova import NovaClient

neutron_client = NeutronClient()
nova_client = NovaClient()
glance_client = GlanceClient()
keystone_client = KeystoneClient()
cinder_client = CinderClient()
