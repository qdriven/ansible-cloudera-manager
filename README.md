# README

Ansible Playbook to create Cloudera Manager and Underline Hadoop Ecosystem.

## Usage

1. Genearte Server Template

Getting the command line help:

```python
python cm_host_generator.py -h
```

2. Generator the hosts files via command line tool

After get the help, input the different parameters to generate the ansible hosts template(file: static in inventory).

3. Run Ansible Playbook

```sh
ansible-playbook -i inventory/static playbooks/bootstrap.yml
```

4. Or run installation Step by Step(Ref the playbook/bookstrap.yml)

```sh
ansible-playbook playbooks/common.yml
.......
```