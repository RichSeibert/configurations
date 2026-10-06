#!/usr/bin/env bash
set -euo pipefail

usage() {
    printf '%s\n' \
        'Usage: bash setup.sh [install|dotfiles|export] [--dry-run]' \
        '  install   Install Vim, Git, tmux, rsync, htop and personal settings (default)' \
        '  dotfiles  Apply personal settings without installing packages' \
        '  export    Copy managed settings from this computer back into the checkout'
}

dry_run=false
mode=install
mode_set=false
for arg in "$@"; do
    case "$arg" in
        --dry-run) dry_run=true ;;
        install|dotfiles|export)
            if "$mode_set"; then
                printf 'Choose only one command.\n' >&2; exit 2
            fi
            mode=$arg
            mode_set=true
            ;;
        --help|-h) usage; exit 0 ;;
        *) printf 'Unknown option: %s\n' "$arg" >&2; usage >&2; exit 2 ;;
    esac
done

run() {
    printf '+'
    printf ' %q' "$@"
    printf '\n'
    if ! "$dry_run"; then
        "$@"
    fi
}

if (( EUID == 0 )) && ! "$dry_run"; then
    printf 'Run as your normal user, not with sudo. Package installs use sudo internally.\n' >&2
    exit 1
fi
install_packages() {
    if [[ ! -r /etc/os-release ]]; then
        printf 'Cannot identify this operating system.\n' >&2
        exit 1
    fi
    . /etc/os-release
    case " ${ID:-} ${ID_LIKE:-} " in
        *debian*|*ubuntu*|*raspbian*)
            run sudo apt-get update
            run sudo apt-get install -y --no-install-recommends \
                ca-certificates vim git tmux rsync htop
            ;;
        *fedora*|*rhel*)
            run sudo dnf install -y ca-certificates vim-enhanced git tmux rsync htop
            ;;
        *) printf 'Unsupported distribution: %s\n' "${ID:-unknown}" >&2; exit 1 ;;
    esac
}

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
resolve_checkout() {
    if [[ -d "$repo_root/configs" && -e "$repo_root/.git" && \
            "$(stat -c %u -- "$repo_root")" == "$(id -u)" ]]; then
        return
    fi
    if [[ "$mode" == export ]]; then
        printf 'Run export from a checkout of this repository.\n' >&2
        exit 1
    fi
    repo_root="$HOME/.local/share/configurations"
    if [[ ! -e "$repo_root" ]]; then
        run mkdir -p -- "$(dirname -- "$repo_root")"
        run git clone https://github.com/RichSeibert/configurations.git "$repo_root"
    elif [[ ! -e "$repo_root/.git" || ! -d "$repo_root/configs" || ! -f "$repo_root/setup.sh" ]]; then
        printf 'Cached checkout is not setup-ready: %s. Update it manually or choose a fresh checkout.\n' "$repo_root" >&2
        exit 1
    fi
}

backup_dir=''
backup_existing() {
    local destination=$1 relative=$2 state_dir
    if [[ ! -e "$destination" && ! -L "$destination" ]]; then
        return
    fi
    if [[ -z "$backup_dir" ]]; then
        state_dir=${XDG_STATE_HOME:-$HOME/.local/state}/configurations/backups
        mkdir -p -- "$state_dir"
        backup_dir=$(mktemp -d "$state_dir/$(date +%Y%m%d-%H%M%S).XXXXXX")
        printf 'Backups: %s\n' "$backup_dir"
    fi
    mkdir -p -- "$backup_dir/$(dirname -- "$relative")"
    cp -a -- "$destination" "$backup_dir/$relative"
}

copy_file() {
    local source=$1 destination=$2 temporary
    if [[ -d "$destination" && ! -L "$destination" ]]; then
        printf 'Expected a file, found a directory: %s\n' "$destination" >&2
        exit 1
    fi
    mkdir -p -- "$(dirname -- "$destination")"
    temporary=$(mktemp "$(dirname -- "$destination")/.configurations.XXXXXX")
    cp -- "$source" "$temporary"
    chmod 644 "$temporary"
    mv -T -- "$temporary" "$destination"
}

sync_dotfiles() {
    local configured relative source destination
    if "$dry_run" && [[ ! -d "$repo_root/configs" ]]; then
        printf 'Would install dotfiles from %s after cloning.\n' "$repo_root"
        return
    fi
    while IFS= read -r -d '' configured; do
        relative=${configured#"$repo_root/configs/"}
        relative=${relative#*/}
        if [[ "$relative" == .bashrc ]]; then
            relative=.config/rich-configurations/bashrc
        fi
        if [[ "$mode" == export ]]; then
            source="$HOME/$relative"
            destination=$configured
            [[ -f "$source" ]] || continue
        else
            source=$configured
            destination="$HOME/$relative"
        fi
        if [[ -f "$destination" ]] && cmp -s -- "$source" "$destination"; then
            continue
        fi
        printf 'Copy: %s -> %s\n' "$source" "$destination"
        if "$dry_run"; then continue; fi
        if [[ "$mode" != export ]]; then backup_existing "$destination" "$relative"; fi
        copy_file "$source" "$destination"
    done < <(find "$repo_root/configs" -type f -print0)
}

install_bash_hook() {
    local hook temporary
    # Keep the distribution's startup file and source personal settings after it.
    hook='[ -f "$HOME/.config/rich-configurations/bashrc" ] && . "$HOME/.config/rich-configurations/bashrc"'
    if grep -Fqx -- "$hook" "$HOME/.bashrc" 2>/dev/null; then return; fi
    printf 'Add managed Bash hook: %s/.bashrc\n' "$HOME"
    if "$dry_run"; then return; fi
    if [[ -d "$HOME/.bashrc" && ! -L "$HOME/.bashrc" ]]; then
        printf 'Expected a file, found a directory: %s/.bashrc\n' "$HOME" >&2
        exit 1
    fi
    backup_existing "$HOME/.bashrc" .bashrc
    temporary=$(mktemp "$HOME/.bashrc.XXXXXX")
    if [[ -e "$HOME/.bashrc" ]]; then
        cp --dereference -- "$HOME/.bashrc" "$temporary"
        chmod --reference="$HOME/.bashrc" "$temporary"
    else
        chmod 644 "$temporary"
    fi
    printf '\n# Rich configurations (managed)\n%s\n' "$hook" >> "$temporary"
    mv -T -- "$temporary" "$HOME/.bashrc"
}

if [[ "$mode" == install ]]; then install_packages; fi
resolve_checkout
sync_dotfiles
if [[ "$mode" == export ]]; then
    printf 'Export complete. Review git diff for private data before committing.\n'
else
    install_bash_hook
    printf 'Setup complete. Open a new shell to load personal settings.\n'
fi
