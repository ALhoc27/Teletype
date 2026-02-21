- ***ссылка на https://docs.oracle.com/en/java/javase/21/docs/api/index.html***
- ***ссылки на сопутствующую информацию***

Метод `indexOf(Object o)` есть во многих классах Java. ==Его основная задача — найти **первое вхождение элемента** в коллекции или строке и вернуть его индекс==. Если элемент не найден, возвращается `-1`.
### Полная сигнатура метода
```java
public int indexOf(Object)
```
`public` - Метод доступен из любого места в коде (модификатор доступа).  
`int` - Возвращаемый тип — индекс элемента (если найден) или `-1` (если элемент не найден).
 &nbsp;
> <span style="font-size: 1.1em; font-weight: bold; margin: 0; line-height: 1.2; display: inline-block; margin-bottom: 10px;"> &nbsp;&nbsp; Детальное объяснение </span>
>   ###### Заголовок
>   &nbsp; * **Не обязательно**, но может быть*
>   &nbsp; 
>   &nbsp;
>
><div class="el-div"><div data-callout-metadata="" data-callout-fold="" data-callout="info" class="callout" style=" margin: 0px;"><div class="callout-title" dir="auto"><div class="callout-icon"><svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="svg-icon lucide-info"><circle cx="12" cy="12" r="10"></circle><path d="M12 16v-4"></path><path d="M12 8h.01"></path></svg></div><div class="callout-title-inner">Заметка</div></div><div class="callout-content">
><p dir="auto" style="line-height: 1.5; margin: 0px;">ТЕКСТ</p>
></div></div></div>
>
>    Или таким блоком
>   <span style="width: 100%; border-collapse: collapse; font-family: Arial, sans-serif; font-size: 15px; text-align: left; padding: 5px 5px; background-color: rgba(255, 165, 0, 0.3); border-radius: 8px; overflow: hidden; box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1); border: 1px solid #d6d8db; line-height: 1.5; display: block;
">В случае большого объема разъяснений делается отдельная страница сноска
</span>


> [!DANGER] Запомни!
> - **Переопределяя `equals()`, всегда переопределяй `hashCode()`**.
> - **Равные объекты должны иметь одинаковый `hashCode()`**.
> - **Нарушение контракта приводит к багам в коллекциях (`HashMap`, `HashSet`)**. [^6]


### Разберём все ключевые реализации:
- <span class="link_color2">**[[java.util.ArrayList]]**</span> － ([indexOf(Object o) > **Реализация `indexOf(o)` в `ArrayList` (JDK 8–21)**](app://obsidian.md/indexOf(Object%20o)#**%D0%A0%D0%B5%D0%B0%D0%BB%D0%B8%D0%B7%D0%B0%D1%86%D0%B8%D1%8F%20%60indexOf(o)%60%20%D0%B2%20%60ArrayList%60%20(JDK%208%E2%80%9321)**))
- <span class="link_color2">**[[java.util.LinkedList]]**</span> －
- *Другие коллекции (`HashMap`, `HashSet`, `TreeSet`) – почему там нет `indexOf()`?*

<div style="height: 4px; background: linear-gradient(to right, #888, #ddd); box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2); margin: 20px 0; border-radius: 2px;"></div>


#### `indexOf(o)` в `ArrayList` 
Возможное уточнение данной реализации...

| <span style="font-size: 1.04em; font-weight: bold; margin: 0; line-height: 1.2; display: inline-block; margin-bottom: 10px; "> &nbsp;&nbsp; Заголовок: </span>                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | 🛠 Разберём пошагово, что происходит:                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| - **==Вносить построчно==**<br>Можно выделить более компактно (⠀), с двумя пробелами, но и стандартное форматирование так же поддерживается<br>**Поставь в коде обычный пробел где пустая строка**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | - **==Вносить построчно==**<br>Можно выделить более компактно (⠀), с двумя пробелами, но и стандартное форматирование так же поддерживается<br>**Поставь в коде обычный пробел где пустая строка**                                                                                                                                                                                                                                                                          |
| <div class="code_md_tab"><br><code class="language-java language-java_td specific-override"><br>import java.util.Objects;<br></code><br><code class="language-java language-java_td specific-override"><br><br></code><br><code class="language-java language-java_td specific-override"><br><br></code><br><code class="language-java language-java_td specific-override"><br><br></code><br><code class="language-java language-java_td specific-override"><br><br></code><br><code class="language-java language-java_td specific-override"><br><br></code><br><code class="language-java language-java_td specific-override"><br><br></code><br><code class="language-java language-java_td specific-override"><br><br></code><br><code class="language-java language-java_td specific-override"><br><br></code>⠀<br><code class="language-java language-java_td specific-override"><br><br></code>⠀⠀⠀⠀⠀<br></div> | <span style="font-size: 1.2em; font-weight: bold; margin: 0; line-height: 1.2; display: inline-block; margin-bottom: 10px;"> &nbsp;🛠 Разберём: </span><br><span style="line-height: 1.5">Допустим, `LinkedList` хранит:<span style="display: inline-block; padding: 0; margin-bottom: 5px;">&nbsp;</span><br><div class="code_md_tab"><br><code class="language-java language-java_td specific-override"><br>import java.util.Objects;<br></code><br></div><br><br></span> |
| Выделить строку можно - 🟤 🟣 🟠 🔵 🔴   <br>Для того что бы выравнять колонки, добавьте на след строке данный пробел (⠀)<br>или попробуйте убрать `display: inline-block; margin-bottom: 10px;`)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | 🔹 **Вызов `list.indexOf("Java")`**:<br>1. `x = first` → `"Java"`, `index = 0` [^1]<br>2. `"Java".equals("Java")` ✅ **Совпадает!**  <br>    → **Возвращаем `0`**<br>❌                                                                                                                                                                                                                                                                                                       |
.....

<div style="height: 4px; background: linear-gradient(to right, #888, #ddd); box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2); margin: 20px 0; border-radius: 2px;"></div>

#### `indexOf(o)` в `LinkedList` 
Возможное уточнение данной реализации...

| <span style="font-size: 1.04em; font-weight: bold; margin: 0; line-height: 1.2; display: inline-block; margin-bottom: 10px; "> &nbsp;&nbsp; Заголовок: </span>                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | 🛠 Разберём пошагово, что происходит:                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| - **==Вносить построчно==**<br>Можно выделить более компактно (⠀), с двумя пробелами, но и стандартное форматирование так же поддерживается<br>**Поставь в коде обычный пробел где пустая строка**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | - **==Вносить построчно==**<br>Можно выделить более компактно (⠀), с двумя пробелами, но и стандартное форматирование так же поддерживается<br>**Поставь в коде обычный пробел где пустая строка**                                                                                                                                                                                                                                                                               |
| <div class="code_md_tab"><br><code class="language-java language-java_td specific-override"><br>import java.util.Objects;<br></code><br><code class="language-java language-java_td specific-override"><br><br></code><br><code class="language-java language-java_td specific-override"><br><br></code><br><code class="language-java language-java_td specific-override"><br><br></code><br><code class="language-java language-java_td specific-override"><br><br></code><br><code class="language-java language-java_td specific-override"><br><br></code><br><code class="language-java language-java_td specific-override"><br><br></code><br><code class="language-java language-java_td specific-override"><br><br></code><br><code class="language-java language-java_td specific-override"><br><br></code>⠀<br><code class="language-java language-java_td specific-override"><br><br></code>⠀⠀⠀⠀⠀<br></div> | <span style="font-size: 1.2em; font-weight: bold; margin: 0; line-height: 1.2; display: inline-block; margin-bottom: 10px;"> &nbsp;🛠 Разберём: </span><br><span style="line-height: 1.5">Допустим, `LinkedList` хранит:<span style="display: inline-block; padding: 0; margin-bottom: 5px;">&nbsp;</span><br><div class="code_md_tab"><br><code class="language-java language-java_td specific-override"><br>import java.util.Objects;<br></code><br></div><br>текст<br></span> |
| Выделить строку можно - 🟤 🟣 🟠 🔵 🔴   <br>Для того что бы выравнять колонки, добавьте на след строке данный пробел (⠀)<br>или попробуйте убрать `display: inline-block; margin-bottom: 10px;`)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | 🔹 **Вызов `list.indexOf("Java")`**:<br>1. `x = first` → `"Java"`, `index = 0` [^1]<br>2. `"Java".equals("Java")` ✅ **Совпадает!**  <br>    → **Возвращаем `0`**<br>❌                                                                                                                                                                                                                                                                                                            |
.....
<div style="height: 4px; background: linear-gradient(to right, #888, #ddd); box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2); margin: 20px 0; border-radius: 2px;"></div>

### Заключение:












<br/>
<div style="text-align: center; margin: 0; padding: 0;"> <span style="color: #ff7e5f; font-size: 20px; display: inline; margin: 10; padding: 0;"> ● </span> <span style="color: #feb47b; font-size: 20px; display: inline; margin: 10; padding: 0;"> ● </span> <span style="color: #4facfe; font-size: 20px; display: inline; margin: 10; padding: 0;"> ● </span> </div>

[^1]:

[^2]:

[^3]:

[^4]:

[^5]:

[^6]:

[^7]:

[^8]:

[^9]:

[^10]:

[^11]:

[^12]:

[^13]:

[^14]:

[^15]:

[^16]:

[^17]:

[^18]:

[^19]:

[^20]:
