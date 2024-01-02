<!-- markdownlint-disable -->

<a href="../src/pebble.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `pebble.py`
The agent pebble service module. 



---

## <kbd>class</kbd> `PebbleService`
The charm pebble service manager. 

<a href="../src/pebble.py#L20"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(state: State)
```

Initialize the pebble service. 



**Args:**
 
 - <b>`state`</b>:  The Jenkins k8s agent state. 




---

<a href="../src/pebble.py#L69"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `reconcile`

```python
reconcile(
    server_url: str,
    agent_token_pair: Tuple[str, str],
    container: Container
) → None
```

Reconcile the Jenkins agent service. 



**Args:**
 
 - <b>`server_url`</b>:  The Jenkins server address. 
 - <b>`agent_token_pair`</b>:  Matching pair of agent name to agent token. 
 - <b>`container`</b>:  The agent workload container. 

---

<a href="../src/pebble.py#L87"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `stop_agent`

```python
stop_agent(container: Container) → None
```

Stop Jenkins agent. 



**Args:**
 
 - <b>`container`</b>:  The agent workload container. 



**Raises:**
 
 - <b>`APIError`</b>:  if something went wrong with pebble requesting service stop. 


