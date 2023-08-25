<!-- markdownlint-disable -->

<a href="../src/metadata.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `metadata.py`
The module for handling agent metadata. 



---

## <kbd>class</kbd> `Agent`
The Jenkins agent metadata. 

Attrs:  num_executors: The number of executors available on the unit.  labels: The comma separated labels to assign to the agent.  name: The name of the agent. 




---

<a href="../src/metadata.py#L36"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_jenkins_agent_v0_interface_dict`

```python
get_jenkins_agent_v0_interface_dict() → Dict[str, str]
```

Generate dictionary representation of agent metadata. 



**Returns:**
  A dictionary adhering to jenkins_agent_v0 interface. 

---

<a href="../src/metadata.py#L24"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_jenkins_slave_interface_dict`

```python
get_jenkins_slave_interface_dict() → Dict[str, str]
```

Generate dictionary representation of agent metadata. 



**Returns:**
  A dictionary adhering to jenkins-slave interface. 


