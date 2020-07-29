import json

from ops.framework import EventBase, EventsBase, EventSource, Object, StoredState


class NewClient(EventBase):
    def __init__(self, handle, client):
        super().__init__(handle)
        self.client = client

    def snapshot(self):
        return {
            'relation_name': self.client._relation.name,
            'relation_id': self.client._relation.id,
        }

    def restore(self, snapshot):
        relation = self.model.get_relation(snapshot['relation_name'], snapshot['relation_id'])
        self.client = HTTPInterfaceClient(relation, self.model.unit)


class HTTPServerEvents(EventsBase):
    new_client = EventSource(NewClient)


class HTTPServer(Object):
    on = HTTPServerEvents()
    state = StoredState()

    def __init__(self, charm, relation_name):
        super().__init__(charm, relation_name)
        self.relation_name = relation_name
        self.framework.observe(charm.on.start, self.init_state)
        self.framework.observe(charm.on[relation_name].relation_joined, self.on_joined)
        self.framework.observe(charm.on[relation_name].relation_departed, self.on_departed)

    def init_state(self, event):
        self.state.apps = []

    @property
    def _relations(self):
        return self.model.relations[self.relation_name]

    def on_joined(self, event):
        if event.app not in self.state.apps:
            self.state.apps.append(event.app)
            self.on.new_client.emit(HTTPInterfaceClient(event.relation, self.model.unit))

    def on_departed(self, event):
        self.state.apps = [app for app in self._relations]

    def clients(self):
        return [HTTPInterfaceClient(relation, self.model.unit) for relation in self._relations]


class HTTPInterfaceClient:
    def __init__(self, relation, local_unit):
        self._relation = relation
        self._local_unit = local_unit
        self.ingress_address = relation.data[local_unit]['ingress-address']

    def serve(self, hosts, port):
        self._relation.data[self._local_unit]['extended_data'] = json.dumps([{
            'hostname': host,
            'port': port,
        } for host in hosts])