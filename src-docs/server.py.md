<!-- markdownlint-disable -->

<a href="../src/server.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `server.py`
Functions to interact with jenkins server. 

**Global Variables**
---------------
- **USER**

---

<a href="../src/server.py#L46"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `download_jenkins_agent`

```python
download_jenkins_agent(server_url: str, container: Container) → None
```

Download Jenkins agent JAR executable from server. 



**Args:**
 
 - <b>`server_url`</b>:  The Jenkins server URL address. 
 - <b>`container`</b>:  The agent workload container. 



**Raises:**
 
 - <b>`AgentJarDownloadError`</b>:  If an error occurred downloading the JAR executable. 


---

<a href="../src/server.py#L68"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `validate_credentials`

```python
validate_credentials(
    agent_name: str,
    credentials: Credentials,
    container: Container,
    add_random_delay: bool = False
) → bool
```

Check if the credentials can be used to register to the server. 



**Args:**
 
 - <b>`agent_name`</b>:  The Jenkins agent name. 
 - <b>`credentials`</b>:  Server credentials required to register to Jenkins server. 
 - <b>`container`</b>:  The Jenkins agent workload container. 
 - <b>`add_random_delay`</b>:  Whether random delay should be added to prevent parallel registration on  server. 



**Returns:**
 True if credentials and agent_name pairs are valid, False otherwise. 


---

<a href="../src/server.py#L124"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `find_valid_credentials`

```python
find_valid_credentials(
    agent_name_token_pairs: Iterable[Tuple[str, str]],
    server_url: str,
    container: Container
) → Optional[Tuple[str, str]]
```

Find credentials that can be applied if available. 



**Args:**
 
 - <b>`agent_name_token_pairs`</b>:  Matching agent name and token pair to check. 
 - <b>`server_url`</b>:  The jenkins server url address. 
 - <b>`container`</b>:  The Jenkins agent workload container. 



**Returns:**
 Agent name and token pair that can be used. None if no pair is available. 


---

## <kbd>class</kbd> `AgentJarDownloadError`
Represents an error downloading agent JAR executable. 





---

## <kbd>class</kbd> `Credentials`
The credentials used to register to the Jenkins server. 

Attrs:  address: The Jenkins server address to register to.  secret: The secret used to register agent. 





---

## <kbd>class</kbd> `ServerBaseError`
Represents errors with interacting with Jenkins server. 





