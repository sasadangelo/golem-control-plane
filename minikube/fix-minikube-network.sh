#!/bin/bash
# *******************************************************************************
# IBM Confidential
# © Copyright IBM Corp. 2022,2026
# ******************************************************************************/

set -e

printf "\n=== 🛡️ Resetting Minikube Network Firewall (Permissive Mode) ===\n\n"

# 1. Pulizia e Apertura Totale iptables
printf "Flushing iptables and setting policy to ACCEPT...\n"

# Rimuove tutte le regole esistenti nella catena FORWARD
minikube ssh -- "sudo iptables -F FORWARD"

# Imposta la Policy predefinita su ACCEPT (se non c'è una regola, accetta)
minikube ssh -- "sudo iptables -P FORWARD ACCEPT"

# Inserisce una regola universale come prima posizione per sicurezza ridondante
minikube ssh -- "sudo iptables -I FORWARD 1 -j ACCEPT"

printf "✓ Firewall fully OPEN (All ports allowed)\n\n"

# Configure Minikube VM resolv.conf to use public DNS servers
printf "Configuring Minikube VM DNS...\n"
minikube ssh -- "sudo sh -c 'echo \"nameserver 8.8.8.8\" > /etc/resolv.conf'"
minikube ssh -- "sudo sh -c 'echo \"nameserver 1.1.1.1\" >> /etc/resolv.conf'"
printf "✓ Minikube VM DNS configured\n\n"

# Configure CoreDNS to use public DNS servers (Google 8.8.8.8 and Cloudflare 1.1.1.1)
printf "Configuring CoreDNS...\n"
kubectl patch configmap coredns -n kube-system --type merge -p '{"data":{"Corefile":".:53 {\n    log\n    errors\n    health {\n       lameduck 5s\n    }\n    ready\n    kubernetes cluster.local in-addr.arpa ip6.arpa {\n       pods insecure\n       fallthrough in-addr.arpa ip6.arpa\n       ttl 30\n    }\n    prometheus :9153\n    hosts {\n       fe80::1 host.minikube.internal\n       fallthrough\n    }\n    forward . 8.8.8.8 1.1.1.1 {\n       max_concurrent 1000\n    }\n    cache 30 {\n       disable success cluster.local\n       disable denial cluster.local\n    }\n    loop\n    reload\n    loadbalance\n}\n"}}'

printf "✓ CoreDNS configured\n\n"

# Restart CoreDNS to apply changes
printf "Restarting CoreDNS...\n"
kubectl rollout restart deployment coredns -n kube-system
kubectl rollout status deployment coredns -n kube-system

printf "✓ CoreDNS restarted\n\n"

# Verify DNS resolution
printf "=== Verifying DNS Resolution ===\n\n"

printf "Testing internal DNS (kubernetes.default)...\n"
if kubectl run test-dns-internal --image=busybox:1.28 --rm -it --restart=Never -- nslookup kubernetes.default 2>/dev/null; then
    printf "✓ Internal DNS working\n\n"
else
    printf "✗ Internal DNS test failed\n\n"
fi

printf "Testing external DNS (google.com)...\n"
if kubectl run test-dns-external --image=busybox:1.28 --rm -it --restart=Never -- nslookup google.com 2>/dev/null; then
    printf "✓ External DNS working\n\n"
else
    printf "✗ External DNS test failed\n\n"
fi

printf "=== Network Fix Complete ===\n\n"
printf "NOTE: These iptables rules are NOT persistent.\n"
printf "You must run this script again after every Mac or Minikube restart.\n\n"