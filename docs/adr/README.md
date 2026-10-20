# Architecture decisions

Short records of the choices that shaped the project. Each one says what we decided and what it costs us.

- [0001. Numbers are computed in code, language comes from models](0001-numbers-in-code-language-in-models.md)
- [0002. Instant overlays first, agent text attaches later](0002-instant-overlays-and-late-text.md)
- [0003. No service keys: Entra ID everywhere](0003-keyless-entra-auth.md)
- [0004. An event bus interface with an in-memory and an Event Hubs version](0004-event-bus-interface.md)
- [0005. Real footage never touches the synthetic engine](0005-real-footage-kept-apart.md)
- [0006. Translator, Speech and Content Safety share the Foundry resource](0006-one-foundry-resource.md)
- [0007. RT-DETR for detection, not Ultralytics YOLO](0007-rtdetr-not-yolo.md)
- [0008. Offside flags are instant triggers, not moments](0008-offside-is-a-trigger.md)
- [0009. Agent output cache: files locally, Cosmos DB in Azure, layered](0009-cosmos-cache-over-files.md)
