<!-- markdownlint-disable -->

<a href="../src/agent.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `agent.py`
The agent relation observer module. 

**Global Variables**
---------------
- **AGENT_RELATION**
- **SLAVE_RELATION**


---

## <kbd>class</kbd> `Observer`
The Jenkins agent relation observer. 

<a href="../src/agent.py#L20"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(charm: CharmBase, state: State, pebble_service: PebbleService)
```

Initialize the observer and register event handlers. 



**Args:**
 
 - <b>`charm`</b>:  The parent charm to attach the observer to. 
 - <b>`state`</b>:  The charm state. 
 - <b>`pebble_service`</b>:  Service manager that controls Jenkins agent service through pebble. 


---

#### <kbd>property</kbd> model

Shortcut for more simple access the model. 




