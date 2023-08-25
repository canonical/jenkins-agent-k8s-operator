<!-- markdownlint-disable -->

<a href="../src/state.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `state.py`
The module for managing charm state. 

**Global Variables**
---------------
- **SLAVE_RELATION**
- **AGENT_RELATION**


---

## <kbd>class</kbd> `CharmStateBaseError`
Represents error with charm state. 





---

## <kbd>class</kbd> `InvalidStateError`
Exception raised when state configuration is invalid. 

<a href="../src/state.py#L32"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: str = '')
```

Initialize a new instance of the InvalidStateError exception. 



**Args:**
 
 - <b>`msg`</b>:  Explanation of the error. 





---

## <kbd>class</kbd> `JenkinsConfig`
The Jenkins config from juju config values. 

Attrs:  server_url: The Jenkins server url.  agent_name_token_pairs: Jenkins agent names paired with corresponding token value. 




---

<a href="../src/state.py#L52"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_charm_config`

```python
from_charm_config(config: ConfigData) → Optional[ForwardRef('JenkinsConfig')]
```

Instantiate JenkinsConfig from charm config. 



**Args:**
 
 - <b>`config`</b>:  Charm configuration data. 



**Returns:**
 JenkinsConfig if configuration exists, None otherwise. 


---

## <kbd>class</kbd> `State`
The k8s Jenkins agent state. 

Attrs:  agent_meta: The Jenkins agent metadata to register on Jenkins server.  jenkins_config: Jenkins configuration value from juju config.  slave_relation_credentials: The full set of credentials from the slave relation. None if  partial data is set.  agent_relation_credentials: The full set of credentials from the agent relation. None if  partial data is set or the credentials do not belong to current agent.  jenkins_agent_service_name: The Jenkins agent workload container name. 




---

<a href="../src/state.py#L153"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_charm`

```python
from_charm(charm: CharmBase) → State
```

Initialize the state from charm. 



**Args:**
 
 - <b>`charm`</b>:  The root k8s Jenkins agent charm. 



**Raises:**
 
 - <b>`InvalidStateError`</b>:  if invalid state values were encountered. 



**Returns:**
 Current state of k8s Jenkins agent. 


