# TODO — Simple Tile Cutter

## Done

### Розділити Mark Seams і Dissolve
Виправлено і протестовано:
- **Mark Seams** — проставляє шви на межах тайлів / кутах / периметрі
- **Dissolve non-seamed edges** — видаляє з меша ребра без шву тільки коли увімкнений Mark Seams

Кейс: людина хоче шви але не хоче чистити сітку.

### Робочий фікс Rotation для довільних кутів
Зроблено робочу версію: bisect-різання тепер використовує origin / rotation / scale Projection Box, а прямокутні тайли лишають окремі кроки по ширині й висоті.

### Візуальний Projection Box / preview тайла
Виконано і протестовано:
- Projection Box візуально відповідає реальному модулю тайла
- preview показується як напівпрозорий куб / паралелепіпед
- preview співпадає з projection/cutting logic
- preview зникає разом із Projection Box після Apply
- polish preview протестовано: backface culling, щільніша прозорість, зелений wire-контур

---

### Vertex Paint Tools
Панель Vertex Paint: вхід/вихід з режиму, кольори R/G/B/White/Black/Custom, параметри пензля, Fill Selected / Fill Object (point і face-corner домени).

---

## Open

> Актуальні тікети: https://github.com/olegivanovtogether/modwall_gn/issues

### UVW Cylinder caps
UVW Cylinder проєктує лише бічну поверхню, потрібна проєкція кришок (caps).

### Texel Density
Texel density ще не повністю вирівняний. Треба окремо перевірити й допрацювати відповідність масштабу текстури між wall/box і cylinder projection.

### Cylinder Angular Sections
Розібратися з формулами січень по окружності: скільки існуючих ребер/сторін циліндра припадає на один tile, коли `Tiles Around` не ділиться рівно на кількість сторін, і як правильно додавати angular cuts без перекосів UV.
