# -*- coding: utf-8 -*-
from optparse import OptionParser

import yaml

inventory_groups = ["hadoop-cluster"
    , "ntp", "kdc", "mariadb", "cm", "hdfs-namenode", "hdfs-journal"
    , "cm-gateway", "yarn-rm", "hbase-nodes", "impala-host"
    , "hive-host", "zk-nodes", "nginx-keepalived", "openldap"]


class AnsibleHost:
    BASE_DESC_TEMPLATE = "{host_name} ansible_host={ip} ansible_ssh_user={user_name} " \
                         "ansible_ssh_pass={password}"

    def __init__(self, ip,
                 host_name,
                 user_name='root',
                 password='123456'):
        self.ip = ip
        self.host_name = host_name
        self.user_name = user_name
        self.password = password

    def base_desc(self):
        """
        get base ansible host inventory description
        :return: base inventory setting
        """
        return self.BASE_DESC_TEMPLATE.format(host_name=self.host_name,
                                              ip=self.ip,
                                              user_name=self.user_name,
                                              password=self.password)

    def desc_with_configs(self, addtl_config={}):
        """
        ansible host inventory description with addtl config
        :param addtl_config: dict for additional configuration
        :return: host inventory setting with additional configuration
        """
        base_desc = self.BASE_DESC_TEMPLATE.format(host_name=self.host_name,
                                                   ip=self.ip,
                                                   user_name=self.user_name,
                                                   password=self.password)
        addtl_config_desc = " ".join([("=".join([k, addtl_config[k]])) for k in addtl_config])

        return " ".join([base_desc, addtl_config_desc])

    def __repr__(self):
        return self.base_desc()

    def __str__(self):
        return self.base_desc()


class HostInventoryGenerator:
    """
    requirement inputs for host inventory generator is
    1. host name
    2. host ip list
    3. additional hosts

    """

    def __init__(self, start_ip, host_name_prefix,
                 hosts_count,
                 additional_hosts=[],
                 host_name_suffix="idc.domain-group",
                 user_name="root",
                 password="123456"):
        self.start_ip = start_ip
        self.host_name_prefix = host_name_prefix
        self.host_name_suffix = host_name_suffix
        self.hosts_count = hosts_count
        self.additional_hosts = additional_hosts
        self.default_user_name = user_name
        self.default_password = password
        self.hostname_start_from = 1
        self.ansible_hosts = []
        self._init_ansible_hosts()
        self.static_output_lines = []

    def _init_ansible_hosts(self):
        """
        init hosts according to :
        1. start_ip
        2. hosts_count
        3. additional_hosts: not in sequence
        4. host_name_prefix
        5. host_name_suffix
        todo: the user/password should be same for all hosts
        :return:
        """
        self.ansible_hosts.append(AnsibleHost(ip=self.start_ip,
                                              host_name=self._host_name(index=1),
                                              user_name=self.default_user_name,
                                              password=self.default_password))
        additional_count = len(self.additional_hosts)
        parsed_ip = self.start_ip.split(".")
        start_ip_index = int(parsed_ip[3])
        ## hosts ip in sequence
        for step in range(1, self.hosts_count - additional_count):
            host_ip = ".".join([".".join(parsed_ip[:-1]), str(start_ip_index + step)])
            self.ansible_hosts.append(AnsibleHost(ip=host_ip,
                                                  host_name=self._host_name(index=step + 1),
                                                  user_name=self.default_user_name,
                                                  password=self.default_password))
        ## hosts ip not in sequence
        for additional_host in self.additional_hosts:
            self.additional_hosts.append(AnsibleHost(ip=additional_host.get("ip"),
                                                     host_name=additional_host.get('host_name'),
                                                     user_name=additional_host.get("user_name", self.default_user_name),
                                                     password=additional_host.get("password", self.default_password)))

    def _host_name(self, index):
        """
        genereate real hostname according to the index
        :param index: host index in the whole cluster,just a naming thing
        :return: string
        """
        return '.'.join([self.host_name_prefix + str(self.hostname_start_from + index - 1),
                         self.host_name_suffix])

    def _generate_group_header(self, group_name):
        """
        generate inventory group header [inventory_group_name]
        :param group_name:
        :return:
        """
        self.static_output_lines.append("[{}]".format(group_name))

    def _generate_singlehost_group(self, group_name, host_index=1, additional_config={}):
        self._generate_group_header(group_name=group_name)
        self.static_output_lines.append(self.ansible_hosts[host_index - 1]
                                        .desc_with_configs(additional_config))

    def _generate_group(self, group_name, host_start_index=1, host_end_index=2, configs={}):
        self._generate_group_header(group_name=group_name)
        for host in self.ansible_hosts[host_start_index - 1:host_end_index]:
            self.static_output_lines.append(host.desc_with_configs(configs))

    def _generate_hadoop_cluster(self):
        self._generate_group_header("hadoop-cluster")
        self.static_output_lines.append(self.ansible_hosts[0].desc_with_configs({"cm": "yes",
                                                                                 "ntp": "yes"}))
        for host in self.ansible_hosts[1:]:
            self.static_output_lines.append(host.base_desc())

    def _generate_ntp(self):
        self._generate_singlehost_group("ntp")

    def _generate_kdc(self):
        self._generate_group_header("kdc")
        self.static_output_lines.append(self.ansible_hosts[0].desc_with_configs({
            "master": "yes"
        }))
        self.static_output_lines.append(self.ansible_hosts[1].desc_with_configs({
            "slave": "yes"
        }))

    def _generate_mariadb(self):
        self._generate_singlehost_group("mariadb")

    def _generate_cm(self):
        self._generate_singlehost_group("cm")

    def _generate_hdfs_namenode(self):
        self._generate_singlehost_group("hdfs-namenode")

    def _generate_hdfs_journal(self):
        self._generate_group("hdfs-journal", host_end_index=3)

    def _generate_cm_gateway(self):
        self._generate_group("cm-gateway", host_start_index=3, host_end_index=4)

    def _generate_yarn_rm(self):
        self._generate_singlehost_group("yarn-rm", host_index=3)

    def _generate_hbase_nodes(self):
        self._generate_group("hbase-nodes",
                             host_start_index=4,
                             host_end_index=6,
                             configs={"backup_master": "yes"})

    def _generate_impala_host(self):
        self._generate_singlehost_group("impala-host", host_index=4)

    def _generate_hive_host(self):
        self._generate_singlehost_group("hive-host", host_index=4)

    def _generate_zk_nodes(self):
        self._generate_group("zk-nodes", host_start_index=3, host_end_index=5)

    def _generate_nginx_keepalived(self):
        self._generate_group_header("nginx-keepalived")
        self.static_output_lines.append(self.ansible_hosts[3].desc_with_configs({
            "master": "yes"
        }))
        self.static_output_lines.append(self.ansible_hosts[4].desc_with_configs({
            "slave": "yes"
        }))

    def _generate_openldap(self):
        self._generate_group_header("openldap")
        self.static_output_lines.append(self.ansible_hosts[0].desc_with_configs({"one": "yes"}))
        self.static_output_lines.append(self.ansible_hosts[1].desc_with_configs({"two": "yes"}))
        self.static_output_lines.append(self.ansible_hosts[2].desc_with_configs({"three": "yes"}))

    def output_static(self):
        """
        Notice: if add one new inventory group, also need to add  generate method
        :return:
        """
        for inventory_group in inventory_groups:
            method = getattr(self, "_generate_" + inventory_group.replace("-", "_"))
            method()
        with open('static', 'w') as f:
            for line in self.static_output_lines:
                f.write(line)
                f.write("\r")


class AnsibleAllParams:
    """
    Default Parameters:
        debug: true
        demo_run: true
        centos_repo_host: '10.214.96.85:86/repo'
        def_bind_eth: eth0
        host_password: bigdata
        #cm version 13 CDH5.8.0 12 CDH5.7.1
        cm_version: 12
        # openldap
        openldap_server_rootpw: 123456
        # kerberos
        krb_realm: TDAC.domain-GROUP.NET
        kdc_port: 88
        krb_admin_port: 749
        # nginx & keepalived
        listen_port: 8008
        server_name: localhost
        virtual_ipaddress: 10.214.128.251

        # check if this id is unique
        virtual_router_id: 55

        # CM comonents
        hive_metastoreserver_host: testbig2.domain.cn
        hue_server_host: testbig2.domain.cn
        impala_catalogserver_host: testbig4.domain.cn
        oozie_server_host: testbig4.domain.cn
        sentry_server_host: testbig5.domain.cn
        solr_server_host: testbig9.domain.cn
        # CM install directory
        dfs_name_dir_list: /dfs/nn1,/dfs/nn2,/dfs/nn3
        dfs_data_dir_list: /dfs/dn1,/dfs/dn2
        yarn_nodemanager_local_dirs: /data/d1/yarn/nm,/data/d2/yarn/nm
        zk_data_dir: /var/lib/zookeeper
        solr_data_dir: /var/lib/solr
    """

    def __init__(self, hosts):
        self.hosts = hosts
        with open('all_template', 'r') as f:
            self.params = yaml.load(f)

        self.params["hive_metastoreserver_host"] = hosts[2].host_name
        self.params["hue_server_host"] = hosts[2].host_name
        self.params["impala_catalogserver_host"] = hosts[3].host_name
        self.params["oozie_server_host"] = hosts[3].host_name
        self.params["sentry_server_host"] = hosts[4].host_name
        self.params["solr_server_host"] = hosts[5].host_name

    def make_configs(self, configs={}):
        for config in configs:
            self.params[config] = configs[config]
        self._output_all()

    def _output_all(self):
        # todo find an ordered dumper
        with open('all', 'w') as f:
            yaml.dump(self.params, f, Dumper=yaml.SafeDumper,
                      allow_unicode=True,
                      default_flow_style=False)


if __name__ == '__main__':

    parser = OptionParser()
    parser.add_option("-m", "--all",
                      dest="all",
                      default=False,
                      help="flag for generate all file")
    parser.add_option("-i", "--start_ip",
                      dest="start_ip",
                      help="start ip in the CDH group")
    parser.add_option("-c", "--hosts_count",
                      dest="hosts_count", default=6,
                      help="Hosts count in a CDH group,default is 6")
    parser.add_option("-a", "--additional_hosts",
                      dest="additional_hosts", default=[],
                      help="Hosts count in a CDH group,default is []")
    parser.add_option("-p", "--host_name_prefix",
                      dest="host_name_prefix", default="cd-cdh",
                      help="host name prefix in a CDH group,default is cd-cdh")
    parser.add_option("-s", "--host_name_suffix",
                      dest="host_name_suffix", default="idc.domain-group",
                      help="host name suffix in a CDH group,default is idc.domain-group")
    parser.add_option("-u", "--user",
                      dest="user_name", default="root",
                      help="default user name in a CDH group,default is root")

    parser.add_option("-d", "--password",
                      dest="password", default="123456",
                      help="default password in a CDH group,default is 123456")

    parser.add_option("-k", "--krb_realm",
                      dest="krb_realm", default="TDAC.domain-GROUP.NET",
                      help="krb_realm in a CDH group,default is TDC.domain-GROUP.NET")

    parser.add_option("-e", "--virtual_ipaddress",
                      dest="virtual_ipaddress", default="10.214.128.251",
                      help="virtual_ipaddress in a CDH group,default is 10.214.128.251")

    parser.add_option("-t", "--virtual_router_id",
                      dest="virtual_router_id", default="55",
                      help="virtual_router_id in a CDH group,default is 55")
    parser.add_option("-v", "--cm_version",
                      dest="cm_version", default="12",
                      help="cm_version in a CDH group,default is 12")

    (options, args) = parser.parse_args()
    print(options)
    print(args)

    if options.start_ip is None:
        print("start ip must be used in the script, please add -i <ip_address> or --start_ip <ip_address>")
        exit(1)

    # start_ip, host_name_prefix,
    # hosts_count,
    # additional_hosts = [],
    # host_name_suffix = "idc.domain-group",
    # user_name = "root",
    # password = "123456"

    hosts = HostInventoryGenerator(start_ip=options.start_ip,
                                   hosts_count=options.hosts_count,
                                   host_name_prefix=options.host_name_prefix,
                                   additional_hosts=options.additional_hosts,
                                   host_name_suffix=options.host_name_suffix,
                                   user_name=options.user_name,
                                   password=options.password)
    hosts.output_static()
    if options.all:
        AnsibleAllParams(hosts.ansible_hosts).make_configs(configs={
            "cm_version": options.cm_version,
            "virtual_router_id": options.virtual_router_id,
            "virtual_ipaddress": options.virtual_ipaddress,
            "krb_realm": options.krb_realm,
            "host_password": hosts.default_password
        })
