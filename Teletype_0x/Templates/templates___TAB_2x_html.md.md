<table class="language-java_td" style="width: 99%; border-collapse: collapse; margin-bottom: 5px;">
	<tr>
		<strong style="font-size: 1.1em; color: #333; color: #1E587F;">Пример таблицы с двумя большими блоками кода:</strong>
    </tr>
    <tr>
        <td style="padding: 5px 10px; border: 1px solid #ddd; background-color: #f2efed">
            <strong style="font-size: 1em; color: #333; line-height: 1.7;"><span style="border: 1px solid black; padding: 2px; color: #BC2032;">#1</span>
		&nbsp; Сравнение без <code>Objects.equals()</code></strong> <!-- Заголовок первой колонки-->
			<br/>
Если вы используете стандартный метод <code>equals()</code>, необходимо учитывать ситуацию с <code>null</code> вручную:
			<br/>
        </td>
        <td style="padding: 5px 10px; border: 1px solid #ddd; background-color: #f2efed">
            <strong style="font-size: 1em; color: #333; line-height: 1.7;"><span style="border: 1px solid black; padding: 2px; color: #007FFF;">#2</span>
		&nbsp; Сравнение с <code>Objects.equals()</code></strong>  <!-- Заголовок второй колонки-->
		<br/>
С <code>Objects.equals()</code> код становится проще и безопаснее:
        </td>
    </tr>
    <tr>
        <td style="padding: 5px 10px; border: 1px solid #ddd;">
            <pre class="language-java_td" style="background-color: #f4f4f4; color: #f8f8f8; margin: 0px; padding: 0px 10px; border-radius: 5px; font-size: 0.9em; overflow-x: auto;">
				<code class="language-java language-java_td" style="font-family: 'Courier New', monospace; padding: 0px; margin: 0px;">
String str1 = null;
String str2 = "Java";
 
// Проверка вручную
if (str1 != null && str1.equals(str2)) {  🔴
    System.out.println("Равны");
} else {
    System.out.println("Не равны");
}
				</code>
            </pre>
        </td>
        <td style="padding: 5px 10px; border: 1px solid #ddd;">
            <pre style="background-color: #f4f4f4; color: #f8f8f8; margin: 0px; padding: 0px 10px; border-radius: 5px; font-size: 0.9em; overflow-x: auto;">
				<code class="language-java language-java_td" style="font-family: 'Courier New', monospace; padding: 0px; margin: 0px;">
String str1 = null;
String str2 = "Java";
 
if (Objects.equals(str1, str2)) {
🔴  System.out.println("Равны");
} else {
    System.out.println("Не равны");
}
				</code>
            </pre>
        </td>
    </tr>
    <tr>
	    <td>
	    Краткое пояснение:
	    </td>
	    <td>
	    Краткое пояснение:
	    </td>
    </tr>
</table>

<span style="font-size: 1.06em; font-weight: 600; margin: 0; line-height: 1.2; display: inline-block; margin-bottom: 0px; color: #5A010B"> Подробнее <span style="border: 1px solid black; padding: 2px; line-height: 1.75; color: #BC2032">#1</span>: &nbsp; </span>
<span class="no-padding-spans">&nbsp;&nbsp;&nbsp; ☝ **Ошибка**: `contains()` использует `hashCode()`, и без корректного `hashCode()` новый объект не будет найден.
</span>

<span style="font-size: 1.06em; font-weight: 600; margin: 0; line-height: 1.2; display: inline-block; margin-bottom: 0px; color: #01356B;"> Подробнее <span style="border: 1px solid black; padding: 2px; line-height: 1.75; color: #007FFF;">#2</span>: &nbsp; </span>
<span class="no-padding-spans">&nbsp;&nbsp;&nbsp; ☝ **Ошибка**: `contains()` использует `hashCode()`, и без корректного `hashCode()` новый объект не будет найден.

</span>


<br/>

 - **Замени все <> на ＜＞**
 - **Поставь в коде пробелы где пустая строка**
 - 🔴 🔵 🟠 ⚫️ 🟤 🟣 **шарик 2 пробела**