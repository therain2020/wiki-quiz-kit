---
type: daily
tags: [daily]
created: "{{date}}"
---
# {{date}}

## Focus

_What's the one thing to accomplish today?_

## Notes

-

## Created Today

```dataview
LIST
FROM ""
WHERE file.cday = date("{{date}}")
SORT file.ctime ASC
```

## Reflections

_End-of-day: what went well, what didn't, what did I learn?_
