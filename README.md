# Jenkins slave operator charm
This charm sets up a jenkins-slave in kubernetes.

To prepare this charm for deployment, run the following to install the
framework in to the `lib/` directory:

```
git submodule add https://github.com/canonical/operator mod/operator
```

Link the framework:
```
ln -s ../mod/operator/ops lib/ops
```


Update the operator submodule:
```
git submodule update --init
```