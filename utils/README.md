# Room Utilities

All room specific code is added here, use `git subtree` to add is a specific directory
in a room code environment

# How to use it

## Adding the utils to a new project

Issue a command to pull the repository into a directory of your choosing. Mine will be `utils` and is always in the root folder of the room:

`git subtree add --prefix=utils git@github.com:MazdakFarzone/room-utils.git fsm --squash`

We add the `--squash` as we don't want to extremlt pollute our current history

After you've added the repo, be sure to update your `python3` environment and all the requirements by running the script:

`./setup_env.sh`

## Fetching changes to the repo

If you want to pull in any new commits to the subtree from the remote, issue the same command as above, replacing `add` for `pull`:

`git subtree pull --prefix=utils git@github.com:MazdakFarzone/room-utils.git fsm --squash`

## Updating repository

If you make a change to anything in `utils` the commit will be stored in the host repository and its logs. That is the biggest change from submodules.

If you now want to update the subtree remote repository with that commit, you must run the same command, excluding `--squash` and replacing `pull` for `push`.

`git subtree push --prefix=utils git@github.com:MazdakFarzone/room-utils.git fsm`

## Example Code

If you feel like looking at some example code, then check out `example_main.py` for inspiration.

## Autostart

Add a `game.desktop` file to `/home/uh/.config/autostart` for autostart capabilities with X-window system. Look at the `.desktop` file for inspiration
