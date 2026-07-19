#!/bin/sh

# 安装或卸载本机 Surge 监控的 macOS LaunchAgent。
set -eu

LABEL="com.rulemesh.surge-monitor"
PYTHON_BIN="/usr/bin/python3"
THROTTLE_INTERVAL="30"
HEALTH_WAIT_SECONDS="${RULEMESH_MONITOR_HEALTH_WAIT_SECONDS:-5}"
SCRIPT_ENTRY=$0
INSTALL_SWAPPED=0
INSTALL_COMMITTED=0
WAS_LOADED=0

die() {
    printf '错误：%s\n' "$*" >&2
    exit 1
}

usage() {
    printf '%s\n' \
        "用法：$SCRIPT_ENTRY [--uninstall]" \
        "" \
        "不带参数时安装并启动 Surge 监控。" \
        "--uninstall 仅卸载 LaunchAgent 并删除 plist，保留全部状态和日志。"
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || die "缺少必需命令：$1"
}

# 不依赖 macOS 缺省不存在的 readlink -f，并限制符号链接跳转次数。
resolve_script_dir() {
    candidate=$SCRIPT_ENTRY
    case "$candidate" in
        /*) ;;
        */*) candidate="$(pwd -P)/$candidate" ;;
        *)
            candidate=$(command -v "$candidate") \
                || die "无法定位安装脚本：$SCRIPT_ENTRY"
            case "$candidate" in
                /*) ;;
                *) candidate="$(pwd -P)/$candidate" ;;
            esac
            ;;
    esac

    link_count=0
    while [ -L "$candidate" ]; do
        link_count=$((link_count + 1))
        [ "$link_count" -le 40 ] || die "安装脚本的符号链接层级异常"
        link_target=$(readlink "$candidate") \
            || die "无法读取安装脚本的符号链接"
        case "$link_target" in
            /*) candidate=$link_target ;;
            *) candidate="$(dirname "$candidate")/$link_target" ;;
        esac
    done

    script_parent=$(dirname "$candidate")
    CDPATH= cd -P "$script_parent" 2>/dev/null \
        || die "无法进入安装脚本目录：$script_parent"
    pwd -P
}

xml_escape() {
    printf '%s' "$1" | sed \
        -e 's/&/\&amp;/g' \
        -e 's/</\&lt;/g' \
        -e 's/>/\&gt;/g' \
        -e 's/"/\&quot;/g' \
        -e "s/'/\&apos;/g"
}

cleanup() {
    set +e
    trap - 0 HUP INT TERM
    if [ "${INSTALL_SWAPPED:-0}" -eq 1 ] && [ "${INSTALL_COMMITTED:-0}" -eq 0 ]; then
        if [ -n "${SERVICE_TARGET:-}" ]; then
            launchctl bootout "$SERVICE_TARGET" >/dev/null 2>&1 || true
        fi
        restore_file "${BACKUP_MONITOR:-}" "$MONITOR_SCRIPT"
        restore_file "${BACKUP_CN_DNS:-}" "$RUNTIME_CN_DNS_DOMAINS"
        restore_file "${BACKUP_PLIST:-}" "$PLIST_PATH"
        BACKUP_MONITOR=""
        BACKUP_CN_DNS=""
        BACKUP_PLIST=""
        INSTALL_SWAPPED=0
        if [ "${WAS_LOADED:-0}" -eq 1 ] && [ -f "$PLIST_PATH" ]; then
            launchctl bootstrap "$DOMAIN_TARGET" "$PLIST_PATH" >/dev/null 2>&1 \
                || printf '错误：异常退出后旧服务无法重新加载\n' >&2
        fi
        printf '错误：安装未提交，已恢复原有运行文件和 plist\n' >&2
    fi
    if [ -n "${TEMP_PLIST:-}" ] && [ -f "$TEMP_PLIST" ]; then
        rm -f "$TEMP_PLIST"
    fi
    if [ -n "${TEMP_MONITOR:-}" ] && [ -f "$TEMP_MONITOR" ]; then
        rm -f "$TEMP_MONITOR"
    fi
    if [ -n "${TEMP_CN_DNS:-}" ] && [ -f "$TEMP_CN_DNS" ]; then
        rm -f "$TEMP_CN_DNS"
    fi
    for backup in "${BACKUP_MONITOR:-}" "${BACKUP_CN_DNS:-}" "${BACKUP_PLIST:-}"; do
        if [ -n "$backup" ] && [ -f "$backup" ]; then
            rm -f "$backup"
        fi
    done
}

backup_file() {
    source_path=$1
    backup_pattern=$2
    if [ -f "$source_path" ]; then
        backup_path=$(mktemp "$backup_pattern") \
            || die "无法创建安装回滚副本"
        cp "$source_path" "$backup_path"
        printf '%s' "$backup_path"
    fi
}

restore_file() {
    backup_path=$1
    target_path=$2
    if [ -n "$backup_path" ] && [ -f "$backup_path" ]; then
        mv -f "$backup_path" "$target_path"
    else
        rm -f "$target_path"
    fi
}

uninstall_agent() {
    if launchctl print "$SERVICE_TARGET" >/dev/null 2>&1; then
        if ! launchctl bootout "$SERVICE_TARGET"; then
            die "无法卸载 ${LABEL}；plist 未删除，请检查 launchctl 输出后重试"
        fi
        printf '已卸载 LaunchAgent：%s\n' "$LABEL"
    else
        printf 'LaunchAgent 当前未加载：%s\n' "$LABEL"
    fi

    if [ -f "$PLIST_PATH" ]; then
        rm -f "$PLIST_PATH"
        printf '已删除 plist：%s\n' "$PLIST_PATH"
    else
        printf '未发现 plist：%s\n' "$PLIST_PATH"
    fi

    printf '状态和日志已保留：%s\n' "$STATE_DIR"
}

install_agent() {
    [ -f "$SOURCE_MONITOR_SCRIPT" ] \
        || die "缺少监控程序：$SOURCE_MONITOR_SCRIPT"
    [ -f "$SOURCE_CN_DNS_DOMAINS" ] \
        || die "缺少国内 DNS 清单：$SOURCE_CN_DNS_DOMAINS"
    [ -x "$PYTHON_BIN" ] \
        || die "缺少可执行的系统 Python：$PYTHON_BIN"

    mkdir -p "$LAUNCH_AGENTS_DIR" "$STATE_DIR" "$RUNTIME_TOOLS_DIR" "$RUNTIME_DNS_DIR"
    chmod 700 "$STATE_DIR"
    touch "$STDOUT_PATH" "$STDERR_PATH"
    chmod 600 "$STDOUT_PATH" "$STDERR_PATH"
    if ! "$PYTHON_BIN" -c 'import pathlib,sys; p=pathlib.Path(sys.argv[1]); compile(p.read_bytes(), str(p), "exec")' "$SOURCE_MONITOR_SCRIPT"; then
        die "监控程序无法通过系统 Python 语法预检；未替换现有服务"
    fi
    TEMP_MONITOR=$(mktemp "$RUNTIME_TOOLS_DIR/.monitor_surge.py.XXXXXX") \
        || die "无法创建监控程序临时副本"
    TEMP_CN_DNS=$(mktemp "$RUNTIME_DNS_DIR/.cn_dns_domains.list.XXXXXX") \
        || die "无法创建国内 DNS 清单临时副本"
    trap cleanup 0
    trap 'exit 129' HUP
    trap 'exit 130' INT
    trap 'exit 143' TERM
    cp "$SOURCE_MONITOR_SCRIPT" "$TEMP_MONITOR"
    cp "$SOURCE_CN_DNS_DOMAINS" "$TEMP_CN_DNS"
    chmod 600 "$TEMP_MONITOR" "$TEMP_CN_DNS"
    TEMP_PLIST=$(mktemp "$LAUNCH_AGENTS_DIR/.${LABEL}.plist.XXXXXX") \
        || die "无法创建临时 plist"

    monitor_script_xml=$(xml_escape "$MONITOR_SCRIPT")
    runtime_root_xml=$(xml_escape "$RUNTIME_ROOT")
    runtime_config_xml=$(xml_escape "$RUNTIME_CONFIG")
    stdout_path_xml=$(xml_escape "$STDOUT_PATH")
    stderr_path_xml=$(xml_escape "$STDERR_PATH")

    cat >"$TEMP_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON_BIN</string>
        <string>$monitor_script_xml</string>
        <string>--config</string>
        <string>$runtime_config_xml</string>
        <string>daemon</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$runtime_root_xml</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>ThrottleInterval</key>
    <integer>$THROTTLE_INTERVAL</integer>
    <key>ProcessType</key>
    <string>Background</string>
    <key>StandardOutPath</key>
    <string>$stdout_path_xml</string>
    <key>StandardErrorPath</key>
    <string>$stderr_path_xml</string>
</dict>
</plist>
EOF

    if ! plutil -lint "$TEMP_PLIST" >/dev/null; then
        die "临时 plist 校验失败；原有 plist 未被替换"
    fi

    chmod 644 "$TEMP_PLIST"
    BACKUP_MONITOR=$(backup_file "$MONITOR_SCRIPT" "$RUNTIME_TOOLS_DIR/.monitor_surge.py.rollback.XXXXXX")
    BACKUP_CN_DNS=$(backup_file "$RUNTIME_CN_DNS_DOMAINS" "$RUNTIME_DNS_DIR/.cn_dns_domains.list.rollback.XXXXXX")
    BACKUP_PLIST=$(backup_file "$PLIST_PATH" "$LAUNCH_AGENTS_DIR/.${LABEL}.plist.rollback.XXXXXX")
    if launchctl print "$SERVICE_TARGET" >/dev/null 2>&1; then
        WAS_LOADED=1
    fi

    INSTALL_SWAPPED=1
    mv -f "$TEMP_MONITOR" "$MONITOR_SCRIPT"
    mv -f "$TEMP_CN_DNS" "$RUNTIME_CN_DNS_DOMAINS"
    mv -f "$TEMP_PLIST" "$PLIST_PATH"
    TEMP_MONITOR=""
    TEMP_CN_DNS=""
    TEMP_PLIST=""

    if [ "$WAS_LOADED" -eq 1 ]; then
        if ! launchctl bootout "$SERVICE_TARGET"; then
            restore_file "$BACKUP_MONITOR" "$MONITOR_SCRIPT"
            restore_file "$BACKUP_CN_DNS" "$RUNTIME_CN_DNS_DOMAINS"
            restore_file "$BACKUP_PLIST" "$PLIST_PATH"
            BACKUP_MONITOR=""
            BACKUP_CN_DNS=""
            BACKUP_PLIST=""
            INSTALL_SWAPPED=0
            die "旧版 ${LABEL} 无法卸载；已恢复原有运行文件和 plist"
        fi
        # launchctl 可能在旧进程刚收到退出信号时短暂拒绝同标签 bootstrap。
        sleep 1
    fi

    if ! launchctl bootstrap "$DOMAIN_TARGET" "$PLIST_PATH"; then
        restore_file "$BACKUP_MONITOR" "$MONITOR_SCRIPT"
        restore_file "$BACKUP_CN_DNS" "$RUNTIME_CN_DNS_DOMAINS"
        restore_file "$BACKUP_PLIST" "$PLIST_PATH"
        BACKUP_MONITOR=""
        BACKUP_CN_DNS=""
        BACKUP_PLIST=""
        INSTALL_SWAPPED=0
        if [ "$WAS_LOADED" -eq 1 ] && [ -f "$PLIST_PATH" ]; then
            if ! launchctl bootstrap "$DOMAIN_TARGET" "$PLIST_PATH"; then
                die "新版 ${LABEL} 加载失败；文件已恢复，但旧服务也无法重新加载"
            fi
        fi
        die "新版 ${LABEL} 加载失败；已恢复并重新加载原有服务"
    fi

    sleep "$HEALTH_WAIT_SECONDS"
    if ! launchctl print "$SERVICE_TARGET" 2>/dev/null | grep -q 'state = running' \
        || ! "$PYTHON_BIN" "$MONITOR_SCRIPT" --config "$RUNTIME_CONFIG" status >/dev/null 2>&1; then
        launchctl bootout "$SERVICE_TARGET" >/dev/null 2>&1 || true
        restore_file "$BACKUP_MONITOR" "$MONITOR_SCRIPT"
        restore_file "$BACKUP_CN_DNS" "$RUNTIME_CN_DNS_DOMAINS"
        restore_file "$BACKUP_PLIST" "$PLIST_PATH"
        BACKUP_MONITOR=""
        BACKUP_CN_DNS=""
        BACKUP_PLIST=""
        INSTALL_SWAPPED=0
        if [ "$WAS_LOADED" -eq 1 ] && [ -f "$PLIST_PATH" ]; then
            if ! launchctl bootstrap "$DOMAIN_TARGET" "$PLIST_PATH"; then
                die "新版 ${LABEL} 健康检查失败；文件已恢复，但旧服务也无法重新加载"
            fi
        fi
        die "新版 ${LABEL} 健康检查失败；已恢复原有安装"
    fi

    INSTALL_COMMITTED=1
    printf 'Surge 监控已安装并启动。\n'
    printf 'LaunchAgent：%s\n' "$PLIST_PATH"
    printf '状态和日志：%s\n' "$STATE_DIR"
}

mode="install"
case "$#" in
    0) ;;
    1)
        case "$1" in
            --uninstall) mode="uninstall" ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                usage >&2
                die "不支持的参数：$1"
                ;;
        esac
        ;;
    *)
        usage >&2
        die "参数过多"
        ;;
esac

require_command dirname
require_command readlink
require_command sed
require_command cp
require_command mv
require_command mktemp
require_command mkdir
require_command chmod
require_command touch
require_command rm
require_command grep
require_command id
require_command sleep
require_command launchctl
require_command plutil

[ -n "${HOME:-}" ] || die "HOME 未设置"
case "$HEALTH_WAIT_SECONDS" in
    ''|*[!0-9]*) die "RULEMESH_MONITOR_HEALTH_WAIT_SECONDS 必须是非负整数" ;;
esac
case "$HOME" in
    /*) ;;
    *) die "HOME 必须是绝对路径" ;;
esac

SCRIPT_DIR=$(resolve_script_dir)
REPO_ROOT=$(CDPATH= cd -P "$SCRIPT_DIR/.." 2>/dev/null && pwd -P) \
    || die "无法解析仓库绝对路径"
case "$REPO_ROOT" in
    /*) ;;
    *) die "仓库路径不是绝对路径：$REPO_ROOT" ;;
esac

LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$LAUNCH_AGENTS_DIR/$LABEL.plist"
STATE_DIR="$HOME/Library/Application Support/RuleMesh/surge-monitor"
SOURCE_MONITOR_SCRIPT="$REPO_ROOT/tools/monitor_surge.py"
SOURCE_CN_DNS_DOMAINS="$REPO_ROOT/rules/dns/cn_dns_domains.list"
RUNTIME_ROOT="$STATE_DIR/runtime"
RUNTIME_TOOLS_DIR="$RUNTIME_ROOT/tools"
RUNTIME_DNS_DIR="$RUNTIME_ROOT/rules/dns"
MONITOR_SCRIPT="$RUNTIME_TOOLS_DIR/monitor_surge.py"
RUNTIME_CN_DNS_DOMAINS="$RUNTIME_DNS_DIR/cn_dns_domains.list"
RUNTIME_CONFIG="$STATE_DIR/config.json"
STDOUT_PATH="$STATE_DIR/monitor.stdout.log"
STDERR_PATH="$STATE_DIR/monitor.stderr.log"
USER_ID=$(id -u) || die "无法读取当前用户 UID"
DOMAIN_TARGET="gui/$USER_ID"
SERVICE_TARGET="$DOMAIN_TARGET/$LABEL"

if [ "$mode" = "uninstall" ]; then
    uninstall_agent
else
    install_agent
fi
