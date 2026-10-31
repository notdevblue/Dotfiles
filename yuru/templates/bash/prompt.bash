# Source LAST from interactive ~/.bashrc; no PROMPT_COMMAND or other shell changes.
# Retain Bash's root/user prompt distinction through \$.
case $- in
    *i*) PS1='\[\e[38;2;@FG_RGB@m\]\w \[\e[38;2;@MINT_RGB@m\]\$\[\e[0m\] ' ;;
esac
