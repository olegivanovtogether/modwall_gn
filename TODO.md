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

### Cylinder Projection: кутові розрізи і кришки
Реалізовано в коді: різання по висоті (`_slice_cylinder_height_bands`), кутові розрізи по `Tiles Around` площинами (`_slice_cylinder_around_sectors`), режим `Stretch Around` без розрізів, кришки з `Project Caps` (`_slice_cylinder_caps_grid`). Лишається візуальна перевірка на циліндрах, де `Tiles Around` не ділиться на кількість сторін (див. Open).

### Vertex Paint Tools
Панель Vertex Paint: вхід/вихід з режиму, кольори R/G/B/White/Black/Custom, параметри пензля, Fill Selected / Fill Object (point і face-corner домени).

---

## Open

> Актуальні тікети: https://github.com/olegivanovtogether/modwall_gn/issues

### UVW Cylinder caps (#1)
UVW Cylinder проєктує лише бічну поверхню: грані з нормаллю вздовж осі отримують UV за кутом, без окремої планарної проєкції кришок.

### Texel Density (#2)
Texel density ще не вирівняний між режимами. Треба перевірити відповідність масштабу текстури між wall/box і cylinder projection на сцені.

### Cylinder: візуальна перевірка кутових розрізів (#3)
Код є, але не підтверджено на практиці: коли `Tiles Around` не ділиться рівно на кількість сторін циліндра, перевірити, що UV не перекошені.

### Прямокутні тайли (#4)
Підтримуються, але квадратні лишаються безпечним варіантом. Перевірити у всіх режимах.

### Застарілий тест
`test_tile_cutter.py` посилається на неіснуючу властивість `rotation` і покриває лише Tile Grid. Оновити або видалити.
