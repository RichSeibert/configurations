# .bashrc

iatest=$(expr index "$-" i)

# Source global definitions
if [ -f /etc/bashrc ]; then
	. /etc/bashrc
fi

export PATH="$HOME/.local/bin:$PATH"
export PATH=/usr/local/cuda/bin${PATH:+:${PATH}}
# temporary, cuda doesn't support higher g++ versions yet
export NVCC_PREPEND_FLAGS="-ccbin /usr/bin/g++-13"

# change default editors (usefull for editing cronjobs with "crontab -e")
export VISUAL=vim
export EDITOR=vim

# vim style
# To see bindings, run "bind -P"
set -o vi
set bell-style none
set show-mode-in-prompt on
set vi-cmd-mode-string "\1\e[2 q\2"
set vi-ins-mode-string "\1\e[6 q\2"
set editing-mode vi

# aliases
alias l="ls -lh"
alias ll="ls -lh"
alias la="ls -lha"

# Expand the history size
export HISTFILESIZE=10000
export HISTSIZE=1000

# Don't put duplicate lines in the history and do not add lines that start with a space
export HISTCONTROL=erasedups:ignoredups:ignorespace

# Check the window size after each command and, if necessary, update the values of LINES and COLUMNS
shopt -s checkwinsize

# Causes bash to append to history instead of overwriting it so if you start a new terminal, you have old session history
shopt -s histappend
PROMPT_COMMAND='history -a'

# Ignore case on auto-completion
# Note: bind used instead of sticking these in .inputrc
if [[ $iatest > 0 ]]; then bind "set completion-ignore-case on"; fi

# Show auto-completion list automatically, without double tab
if [[ $iatest > 0 ]]; then bind "set show-all-if-ambiguous On"; fi

# Only show the first 3 dirs in the current path
PS1='\[\e[32m\]$(echo "${PWD/#$HOME/~}" | awk -F/ '\''{if (NF>3) print $(NF-2)"/"$(NF-1)"/"$NF; else print $0}'\'')\[\e[0m\]$ '
