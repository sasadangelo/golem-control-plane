#!/bin/bash
# *******************************************************************************
# IBM Confidential
# © Copyright IBM Corp. 2022,2026
# ******************************************************************************/

set -e

printf "\n=== Checking Minikube Network Status (Permissive Mode) ===\n\n"

FORWARD_POLICY_OK=0
FORWARD_ACCEPT_RULE_OK=0
COREDNS_CONFIG_OK=0
COREDNS_PODS_OK=0
INTERNAL_DNS_OK=0
EXTERNAL_DNS_OK=0

# Check if Minikube is running
printf "1. Checking Minikube status...\n"
if ! minikube status &>/dev/null; then
    printf "✗ Minikube is not running\n"
    printf "  Run: minikube start --driver=podman --container-runtime=cri-o --cpus=4 --memory=7900\n\n"
    exit 1
fi
printf "✓ Minikube is running\n\n"

# Check iptables rules for permissive mode
printf "2. Checking iptables permissive configuration...\n"
IPTABLES_OUTPUT=$(minikube ssh -- sudo iptables -L FORWARD -n -v 2>/dev/null)
IPTABLES_POLICY=$(minikube ssh -- sudo iptables -L FORWARD 2>/dev/null | head -1)

# Check if FORWARD policy is ACCEPT
if echo "$IPTABLES_POLICY" | grep -q "policy ACCEPT"; then
    FORWARD_POLICY_OK=1
    printf "✓ FORWARD chain policy is ACCEPT (permissive mode)\n"
else
    printf "✗ FORWARD chain policy is NOT ACCEPT\n"
    printf "  Current policy: %s\n" "$IPTABLES_POLICY"
    printf "  Network may be restricted\n"
fi

# Check for universal ACCEPT rule at position 1
if echo "$IPTABLES_OUTPUT" | head -3 | grep -q "ACCEPT.*0.*--.*\*.*\*.*0.0.0.0/0.*0.0.0.0/0"; then
    FORWARD_ACCEPT_RULE_OK=1
    printf "✓ Universal ACCEPT rule found at top of chain\n"
else
    printf "✗ Universal ACCEPT rule NOT found at top of chain\n"
    printf "  Some traffic may be blocked\n"
fi

printf "\nCurrent FORWARD chain configuration:\n"
echo "$IPTABLES_POLICY"
printf "\nFirst 10 rules:\n"
echo "$IPTABLES_OUTPUT" | head -12
printf "\n"

# Check CoreDNS configuration
printf "3. Checking CoreDNS configuration...\n"
COREDNS_CONFIG=$(kubectl get configmap coredns -n kube-system -o yaml 2>/dev/null | grep -A 2 "forward")

if echo "$COREDNS_CONFIG" | grep -q "8.8.8.8"; then
    COREDNS_CONFIG_OK=1
    printf "✓ CoreDNS configured with public DNS servers\n\n"
else
    printf "✗ CoreDNS NOT configured with public DNS servers\n"
    printf "  DNS resolution may fail\n\n"
fi

# Check CoreDNS pods status
printf "4. Checking CoreDNS pods...\n"
COREDNS_STATUS=$(kubectl get pods -n kube-system -l k8s-app=kube-dns -o wide 2>/dev/null)
if echo "$COREDNS_STATUS" | grep -q "Running"; then
    COREDNS_PODS_OK=1
    printf "✓ CoreDNS pods are running\n"
    printf "%s\n\n" "$COREDNS_STATUS"
else
    printf "✗ CoreDNS pods are NOT running\n"
    printf "%s\n\n" "$COREDNS_STATUS"
fi

# Test internal DNS resolution
printf "5. Testing internal DNS resolution (kubernetes.default)...\n"
if kubectl run test-dns-internal --image=busybox:1.28 --rm -it --restart=Never -- nslookup kubernetes.default 2>/dev/null | grep -q "Address 1:"; then
    INTERNAL_DNS_OK=1
    printf "✓ Internal DNS resolution working\n\n"
else
    printf "✗ Internal DNS resolution FAILED\n"
    printf "  Pods cannot resolve Kubernetes service names\n\n"
fi

# Test external DNS resolution
printf "6. Testing external DNS resolution (google.com)...\n"
if kubectl run test-dns-external --image=busybox:1.28 --rm -it --restart=Never -- nslookup google.com 2>/dev/null | grep -q "Address 1:"; then
    EXTERNAL_DNS_OK=1
    printf "✓ External DNS resolution working\n\n"
else
    printf "✗ External DNS resolution FAILED\n"
    printf "  Pods cannot resolve external domain names\n\n"
fi

# Summary
printf "=== Network Check Summary ===\n\n"

# Count issues
ISSUES=0

if [ "$FORWARD_POLICY_OK" -ne 1 ]; then
    ISSUES=$((ISSUES + 1))
fi

if [ "$FORWARD_ACCEPT_RULE_OK" -ne 1 ]; then
    ISSUES=$((ISSUES + 1))
fi

if [ "$COREDNS_CONFIG_OK" -ne 1 ]; then
    ISSUES=$((ISSUES + 1))
fi

if [ "$COREDNS_PODS_OK" -ne 1 ]; then
    ISSUES=$((ISSUES + 1))
fi

if [ "$INTERNAL_DNS_OK" -ne 1 ]; then
    ISSUES=$((ISSUES + 1))
fi

if [ "$EXTERNAL_DNS_OK" -ne 1 ]; then
    ISSUES=$((ISSUES + 1))
fi

if [ $ISSUES -eq 0 ]; then
    printf "✅ All network checks passed! Network is in permissive mode and working correctly.\n\n"
    exit 0
else
    printf "⚠️  Found %d issue(s) with network configuration.\n\n" "$ISSUES"
    printf "To fix network issues, run:\n"
    printf "  ./fix-minikube-network.sh\n\n"
    exit 1
fi