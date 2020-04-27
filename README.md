# Jenkins slave operator charm
This charm sets up a jenkins-slave in kubernetes.

To prepare this charm for deployment, run the following to install the
framework in to the `lib/` directory:

```
pip install -t lib/ https://github.com/canonical/operator
```

Link the framework:
```
ln -s ../mod/operator/ops lib/ops
```
