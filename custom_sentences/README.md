# TaskMate voice intents

TaskMate registers Home Assistant [conversation intents](https://www.home-assistant.io/integrations/conversation/)
so you can ask Assist (voice or text) about chores and points:

- *"How many chores does Malia have left?"* → `TaskMateChoresLeft`
- *"How many stars does Alex have?"* → `TaskMatePoints`
- *"Mark make bed as done for Malia"* → `TaskMateCompleteChore`
- *"What's Malia's next job?"* → `TaskMateNextChore`
- *"How close is Alex to the cinema trip?"* → `TaskMateRewardProgress`

Completing a chore by voice counts as the child's own tap: approval rules
apply as usual, and the linked-child setting decides whether the speaker may
act for that child. Chores that need a photo, a number or a note are left for
the child's card. Replies are spoken in Home Assistant's language.

The intent **handlers** ship with the integration and are registered
automatically. The **sentences** that trigger them are matched by HA's default
conversation agent, which loads them from your config's `custom_sentences/<lang>/`
folder.

## Install the sentences

Copy the file for your language (`en`, `da`, `de`, `fr`, `nb`, `nn`, `pl`, `pt` or
`pt-BR`) from this folder into your Home Assistant config, e.g. for English:

```
<config>/custom_sentences/en/taskmate.yaml
```

Then restart Home Assistant (or reload the conversation integration). Ask Assist
one of the sentences above — `{child}` matches any of your children by name. (Older copies of this file used
`{name}`, which Home Assistant reserves for device names — replace them with
these.)

Other languages: copy a file under the matching language code and translate
the `sentences:` lines; the intent names and `lists` keys must stay unchanged.
